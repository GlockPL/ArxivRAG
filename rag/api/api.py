import json
import logging
import random
import uuid

import bcrypt
from fastapi import FastAPI, Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List, Optional, Dict, AsyncGenerator
from datetime import datetime, timedelta, UTC
from jose import JWTError, jwt
import asyncio
import redis
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

from rag.settings import DBSettings, TokenSettings, RedisSettings
from rag.db.db_objects import User, LoginHistory, ConversationTitle, Base, CheckpointBlob, CheckpointWrite, Checkpoint
from rag.rag_pipeline import RAG

db_settings = DBSettings()
token_settings = TokenSettings()
redis_settings = RedisSettings()

redis_client = redis.Redis(
    host=redis_settings.redis_host,
    port=redis_settings.redis_port,
    db=redis_settings.redis_db,
    decode_responses=True
)

postgres_db_uri = f"postgresql://{db_settings.user}:{db_settings.password}@{db_settings.host}:{db_settings.db_port}/{db_settings.user}?sslmode=disable"
engine = create_engine(postgres_db_uri)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

rag = RAG()

app = FastAPI(title="Chat API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----- Pydantic Models for API -----

class UserBase(BaseModel):
    username: str
    email: EmailStr
    name: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenData(BaseModel):
    username: Optional[str] = None
    token_type: Optional[str] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    content: str
    type: str
    thread_id: str


class ConversationCreate(BaseModel):
    title: str
    participants: List[str]  # List of usernames


class ConversationResponse(BaseModel):
    thread_id: str
    title: str
    created_at: datetime
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class ChatSummary(BaseModel):
    thread_id: str
    title: str
    created_at: datetime
    last_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class RefreshRequest(BaseModel):
    refresh_token: str

# In-memory message queue for streaming
user_message_queues: Dict[int, asyncio.Queue] = {}


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

def verify_password(plain_password, hashed_password):
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


def get_password_hash(password):
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
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, token_settings.secret_key, algorithm=token_settings.algorithm)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    to_encode.update({"token_type": "refresh"})

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=7)  # Default 7 days

    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, token_settings.secret_key, algorithm=token_settings.algorithm)
    return encoded_jwt, expire


async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, token_settings.secret_key, algorithms=[token_settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


# ----- Chat Functions -----

def get_user_conversations(db: Session, user_id: int, limit: int = 12, offset: int = 0):
    return db.query(ConversationTitle).filter(ConversationTitle.user_id == user_id).order_by(
        desc(ConversationTitle.created_at)).offset(offset).limit(limit).all()


def get_user_conversation_count(db: Session, user_id: int):
    return db.query(ConversationTitle).filter(ConversationTitle.user_id == user_id).count()

def get_user_conversation_newest(db: Session, user_id: int):
    return db.query(ConversationTitle).filter(ConversationTitle.user_id == user_id).order_by(
        desc(ConversationTitle.created_at)).first()

def get_one_conversation(db: Session, thread_id: str):
    logging.info(f"get_one_conversation: {thread_id}")
    return db.query(ConversationTitle).filter(ConversationTitle.thread_id == thread_id).first()


def get_messages(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}

    state_history = list(rag.get_state_history(config))
    conversation = []
    messages_list = []
    if len(state_history) > 0:
        conversation = state_history[0][0]['messages']

    for message in conversation:
        if isinstance(message, HumanMessage):
            msg_type = "human"
        elif isinstance(message, AIMessage):
            msg_type = "ai"
        else:
            continue

        if not message.content:
            continue

        message_state = MessageResponse(content=message.content, type=msg_type, thread_id=thread_id)
        messages_list.append(message_state)

    return messages_list


# ----- API Endpoints -----

@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Check if email exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        name=user.name,
        password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/token", response_model=Token)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db),
        in_request: Request = None
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Record login history
    login_record = LoginHistory(
        user_id=user.id,
        ip_address=in_request.client.host if in_request else None,
        user_agent=in_request.headers.get("user-agent") if in_request else None
    )
    db.add(login_record)
    db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=token_settings.token_expires_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Create refresh token
    refresh_token_expires = timedelta(days=token_settings.refresh_token_expires_days)
    refresh_token, expire_time = create_refresh_token(
        data={"sub": user.username},
        expires_delta=refresh_token_expires
    )

    # Store refresh token in Redis
    token_expires_seconds = int(refresh_token_expires.total_seconds())
    store_refresh_token(user.id, refresh_token, token_expires_seconds)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.post("/refresh", response_model=Token)
async def refresh_access_token(
        refresh_data: RefreshRequest,
        db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    refresh_token = refresh_data.refresh_token

    # Check if token is blacklisted
    if is_token_blacklisted(refresh_token):
        raise credentials_exception

    try:
        # Decode token to validate it
        payload = jwt.decode(refresh_token, token_settings.secret_key, algorithms=[token_settings.algorithm])
        username = payload.get("sub")
        token_type = payload.get("token_type")

        # Ensure it's a refresh token
        if token_type != "refresh":
            raise credentials_exception

        # Get user from database
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception

        # Validate token exists in Redis
        user_id = validate_refresh_token(refresh_token)
        if user_id is None or user_id != user.id:
            raise credentials_exception

        # Invalidate the used refresh token (one-time use)
        invalidate_refresh_token(refresh_token)

        # Create new access token
        access_token_expires = timedelta(minutes=token_settings.token_expires_minutes)
        new_access_token = create_access_token(
            data={"sub": username},
            expires_delta=access_token_expires
        )

        # Create new refresh token
        refresh_token_expires = timedelta(days=token_settings.refresh_token_expires_days)
        new_refresh_token, expire_time = create_refresh_token(
            data={"sub": username},
            expires_delta=refresh_token_expires
        )

        # Store new refresh token
        token_expires_seconds = int(refresh_token_expires.total_seconds())
        store_refresh_token(user.id, new_refresh_token, token_expires_seconds)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

    except JWTError:
        raise credentials_exception


def logout_operation(request: Request):
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


@app.post("/logout")
async def logout(
        request: Request,
        refresh_token: str = None,
):
    logout_operation(request)

    # Invalidate refresh token if provided
    if refresh_token:
        invalidate_refresh_token(refresh_token)

    return {"detail": "Successfully logged out"}


@app.post("/logout-all")
async def logout_all_devices(
        request: Request,
        current_user: User = Depends(get_current_user)
):
    logout_operation(request)
    # Invalidate all refresh tokens for user
    invalidate_all_user_tokens(current_user.id)

    return {"detail": "Successfully logged out from all devices"}


@app.post("/validate-token")
async def validate_token(token: str = Depends(oauth2_scheme)):
    """
    Validates if a token is valid and not expired.
    This endpoint accepts the token via the Authorization header.
    Returns the username if valid, otherwise throws an authentication error.
    """
    # Check if token is blacklisted
    if is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, token_settings.secret_key, algorithms=[token_settings.algorithm])
        username: str = payload.get("sub")
        token_type: str = payload.get("token_type")

        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Ensure we're using an access token
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify the user exists
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Return basic user info
            return {
                "valid": True,
                "username": username,
                "user_id": user.id
            }
        finally:
            db.close()

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/conversation/newest", response_model=ConversationResponse)
async def get_newest_conversation(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):

    convo = get_user_conversation_newest(db, current_user.id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    conversation = ConversationResponse(
        thread_id=convo.thread_id,
        title=convo.title,
        created_at=convo.created_at,
        user_id=current_user.id,
    )
    return conversation

@app.get("/conversations/count", response_model=dict)
async def count_conversations(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    count = get_user_conversation_count(db, current_user.id)
    return {"total": count}


@app.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
        limit: int = Query(10, ge=1, le=100, description="Number of conversations to return"),
        offset: int = Query(0, ge=0, description="Number of conversations to skip"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    user_convos = get_user_conversations(db, current_user.id, limit, offset)

    convos = []
    for convo in user_convos:
        particular_convo = ConversationResponse(
            thread_id=convo.thread_id,
            title=convo.title,
            created_at=convo.created_at,
            user_id=current_user.id,
        )
        convos.append(particular_convo)

    return convos


async def stream_generator(query: str, thread_id: str, user_id: int) -> AsyncGenerator[str, None]:
    try:
        # Send an initial event to establish the connection and provide thread_id
        json_ret = json.dumps({"type": "connection_established", "content": "[START}" ,"thread_id": thread_id})
        yield f"data: {json_ret}\n\n"

        # Stream content from RAG
        for token in rag.stream(query=query, thread_id = thread_id, user_id = user_id):
            # Add thread_id to each token message
            message_data = {"type": "message", "content": token, "thread_id": thread_id}
            # Ensure the message is properly JSON escaped
            escaped_message = json.dumps(message_data)
            # Format as a proper SSE message
            yield f"data: {escaped_message}\n\n"
            # Force flush with a small delay to ensure incremental delivery
            await asyncio.sleep(0.1)

    except Exception as e:
        print(f"Error in streaming: {str(e)}")
        error_msg = json.dumps({"type": "error", "content": str(e), "thread_id": thread_id})
        yield f"data: {error_msg}\n\n"

    json_ret = json.dumps({"type": "streaming_finished", "content": "[DONE]", "thread_id": thread_id})
    # Send an end message with thread_id
    yield f"data: {json_ret}\n\n"

def generate_unique_thread_id(db: Session) -> str:
    new_thread_id = generate_thread_id()
    while True:
        # Check if conversation exists
        convo = get_one_conversation(db, new_thread_id)
        if not convo:
            return new_thread_id
        new_thread_id = generate_thread_id()

@app.get("/conversations/stream")
async def stream_messages(
        query: str,
        thread_id: str = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    logging.info(f"I'm in conversation {thread_id}")
    # Check if thread_id exists in database
    if thread_id:
        convo = get_one_conversation(db, thread_id)
        if not convo:
            # Thread ID was provided but doesn't exist, generate a new one
            thread_id = generate_unique_thread_id(db)
        elif convo.user_id != current_user.id:
            # Thread exists but belongs to another user
            raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
    else:
        # No thread_id provided, generate a new one
        thread_id = generate_unique_thread_id(db)

    # Set response headers
    headers = {
        "X-Thread-ID": thread_id,
        "Access-Control-Expose-Headers": "X-Thread-ID",
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    # Return a StreamingResponse
    return StreamingResponse(
        stream_generator(query, thread_id, current_user.id),
        media_type="text/event-stream",
        headers=headers
    )




@app.get("/conversations/{thread_id}", response_model=ConversationResponse)
async def get_conversation(
        thread_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Check if conversation exists and user has access
    convo = get_one_conversation(db, thread_id)
    logging.info(f"I'm in conversation {thread_id}")
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # In a real app with multiple participants, check if user is a participant
    if convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    conversation = ConversationResponse(
        thread_id=convo.thread_id,
        title=convo.title,
        created_at=convo.created_at,
        user_id=current_user.id,
    )
    return conversation


@app.get("/conversations/{thread_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
        thread_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Check if conversation exists and user has access
    convo = get_one_conversation(db, thread_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    # Get messages
    messages = get_messages(thread_id)
    return messages


def generate_thread_id() -> str:
    new_thread_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"id_{new_thread_id}_{random.randint(0, 100000)}"




@app.put("/conversations/{thread_id}", response_model=ConversationResponse)
async def update_conversation_title(
        thread_id: str,
        title: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Check if conversation exists and user has access
    convo = get_one_conversation(db, thread_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if user owns the conversation
    if convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this conversation")

    # Update the title
    convo.title = title
    db.commit()
    db.refresh(convo)

    return convo


@app.delete("/conversations/{thread_id}", response_model=dict)
async def delete_conversation(
        thread_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Check if conversation exists and user has access
    convo = get_one_conversation(db, thread_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if user owns the conversation
    if convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this conversation")

    # Delete all checkpoint data related to this thread_id
    # Start with checkpoint_blobs
    db.query(CheckpointBlob).filter(CheckpointBlob.thread_id == thread_id).delete()

    # Delete checkpoint_writes
    db.query(CheckpointWrite).filter(CheckpointWrite.thread_id == thread_id).delete()

    # Delete checkpoints
    db.query(Checkpoint).filter(Checkpoint.thread_id == thread_id).delete()

    # Finally delete the conversation itself
    db.delete(convo)

    # Commit all changes
    db.commit()

    return {"message": f"Conversation {thread_id} and all associated checkpoints deleted successfully"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
