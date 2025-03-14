import logging
import uuid
from datetime import timedelta, datetime, UTC
import random
from typing import Optional

import bcrypt
import redis
from jose import jwt
from sqlalchemy import desc
from sqlalchemy.orm import Session
from fastapi import Request

from rag.db.db_objects import User, ConversationTitle
from rag.settings import RedisSettings, TokenSettings

redis_settings = RedisSettings()
token_settings = TokenSettings()

redis_client = redis.Redis(
    host=redis_settings.redis_host,
    port=redis_settings.redis_port,
    db=redis_settings.redis_db,
    decode_responses=True
)


# ----- Token Management in Redis -----

def add_to_blacklist(token: str, expires_in: int):
    """Add a token to the blacklist (used tokens)"""
    try:
        redis_client.setex(f"bl_token:{token}", expires_in, "1")
        return True
    except Exception as e:
        print(f"Redis error: {str(e)}")
        return False


def is_token_blacklisted(token: str) -> bool:
    """Check if a token is blacklisted"""
    try:
        return bool(redis_client.exists(f"bl_token:{token}"))
    except Exception as e:
        print(f"Redis error: {str(e)}")
        return False


def store_refresh_token(user_id: int, token: str, expires_in: int):
    """Store a refresh token for a user"""
    try:
        # Create user's token set if it doesn't exist
        user_token_key = f"user:{user_id}:refresh_tokens"
        redis_client.sadd(user_token_key, token)
        # Set expiration for this specific token
        redis_client.setex(f"refresh_token:{token}", expires_in, str(user_id))
        return True
    except Exception as e:
        print(f"Redis error: {str(e)}")
        return False


def validate_refresh_token(token: str) -> Optional[int]:
    """Validate a refresh token and return the user ID if valid"""
    try:
        user_id = redis_client.get(f"refresh_token:{token}")
        if user_id:
            return int(user_id)
        return None
    except Exception as e:
        print(f"Redis error: {str(e)}")
        return None


def invalidate_refresh_token(token: str) -> bool:
    """Invalidate a single refresh token"""
    try:
        # Get user ID associated with this token
        user_id = redis_client.get(f"refresh_token:{token}")
        if user_id:
            # Remove token from user's set
            redis_client.srem(f"user:{user_id}:refresh_tokens", token)
        # Delete the token itself
        redis_client.delete(f"refresh_token:{token}")
        return True
    except Exception as e:
        print(f"Redis error: {str(e)}")
        return False


def invalidate_all_user_tokens(user_id: int) -> bool:
    """Invalidate all refresh tokens for a user"""
    try:
        user_token_key = f"user:{user_id}:refresh_tokens"
        tokens = redis_client.smembers(user_token_key)

        # Delete each token
        for token in tokens:
            redis_client.delete(f"refresh_token:{token}")

        # Delete the user's token set
        redis_client.delete(user_token_key)
        return True
    except Exception as e:
        print(f"Redis error: {str(e)}")
        return False


# ----- Security Functions -----

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a hashed password against the plain password"""
    # Convert inputs to bytes if they're not already
    if isinstance(plain_password, str):
        password_bytes = plain_password.encode('utf-8')
    else:
        password_bytes = plain_password

    if isinstance(hashed_password, str):
        hashed_bytes = hashed_password.encode('utf-8')
    else:
        hashed_bytes = hashed_password

    # Verify the password
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """
    Compute a hashed password from a plain password
    """
    # Convert password to bytes if it's not already
    if isinstance(password, str):
        password_bytes = password.encode('utf-8')
    else:
        password_bytes = password

    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)

    # Return the hashed password as a string
    return hashed_password.decode('utf-8')


def authenticate_user(db: Session, username: str, password: str):
    """Authenticate a user"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Generate access token by encoding username and expiration time
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=token_settings.token_expires_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, token_settings.secret_key, algorithm=token_settings.algorithm)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None)-> tuple[str, datetime]:
    """
    Generate a new refresh token by encoding username and expiration time
    """
    to_encode = data.copy()
    to_encode.update({"token_type": "refresh"})

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=token_settings.refresh_token_expires_days)

    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, token_settings.secret_key, algorithm=token_settings.algorithm)
    return encoded_jwt, expire


def logout_operation(request: Request):
    """
    Logout user by blacklisting refresh token
    """
    # Blacklist current access token
    token = None
    for auth in request.headers.getlist("Authorization"):
        if auth.startswith("Bearer "):
            token = auth[7:]

    if token:
        try:
            payload = jwt.decode(token, token_settings.secret_key, algorithms=[token_settings.algorithm],
                                 options={"verify_exp": False})
            exp = payload.get("exp")
            if exp:
                remaining = exp - datetime.now(UTC).timestamp()
                if remaining > 0:
                    add_to_blacklist(token, int(remaining))
        except Exception as e:
            print(f"Error blacklisting token: {str(e)}")


# ----- Chat Functions -----

def get_user_conversations(db: Session, user_id: int, limit: int = 12, offset: int = 0):
    """
    Get conversations for a user, paginated by limit and offset, conversation are returned from newest to oldest
    """
    return db.query(ConversationTitle).filter(ConversationTitle.user_id == user_id).order_by(
        desc(ConversationTitle.created_at)).offset(offset).limit(limit).all()


def get_user_conversation_count(db: Session, user_id: int):
    """
    Counts all conversations for a user
    """
    return db.query(ConversationTitle).filter(ConversationTitle.user_id == user_id).count()


def get_user_conversation_newest(db: Session, user_id: int):
    """
    Returns newest conversations for a user
    """
    return db.query(ConversationTitle).filter(ConversationTitle.user_id == user_id).order_by(
        desc(ConversationTitle.created_at)).first()


def get_one_conversation(db: Session, thread_id: str):
    """
    Get one conversation by thread_id
    """
    logging.info(f"get_one_conversation: {thread_id}")
    return db.query(ConversationTitle).filter(ConversationTitle.thread_id == thread_id).first()


def generate_thread_id() -> str:
    """
    Generate thread_id
    """
    new_thread_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"id_{new_thread_id}_{random.randint(0, 100000)}"


def generate_unique_thread_id(db: Session) -> str:
    """
    Generate unique thread_id by randomly generating thread_id
    """
    new_thread_id = generate_thread_id()
    while True:
        # Check if conversation exists
        convo = get_one_conversation(db, new_thread_id)
        if not convo:
            return new_thread_id
        new_thread_id = generate_thread_id()
