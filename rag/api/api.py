from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, AsyncGenerator
from datetime import datetime, timedelta, UTC
from jose import JWTError, jwt
from passlib.context import CryptContext
import asyncio
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

from rag.settings import DBSettings, TokenSettings
from rag.db.db_objects import User, LoginHistory, ConversationTitle, Base
from rag.rag_pipeline import RAG

db_settings = DBSettings()
token_settings = TokenSettings()

postgres_db_uri = f"postgresql://{db_settings.user}:{db_settings.password}@{db_settings.host}:{db_settings.db_port}/{db_settings.user}?sslmode=disable"
engine = create_engine(postgres_db_uri)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

    class Config:
        orm_mode = True


class TokenData(BaseModel):
    username: Optional[str] = None


class Token(BaseModel):
    access_token: str
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

    class Config:
        orm_mode = True


class ChatSummary(BaseModel):
    thread_id: str
    title: str
    created_at: datetime
    last_message: Optional[str] = None

    class Config:
        orm_mode = True


# In-memory message queue for streaming
user_message_queues: Dict[int, asyncio.Queue] = {}


# ----- Security Functions -----

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


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

def get_user_conversations(db: Session, user_id: int):
    return db.query(ConversationTitle).filter(ConversationTitle.user_id == user_id).order_by(
        desc(ConversationTitle.created_at)).all()


def get_one_conversation(db: Session, thread_id: str):
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
        request: Request = None
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
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None
    )
    db.add(login_record)
    db.commit()

    access_token_expires = timedelta(minutes=token_settings.token_expires_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/validate-token")
async def validate_token(token: str = Depends(oauth2_scheme)):
    """
    Validates if a token is valid and not expired.
    This endpoint accepts the token via the Authorization header.
    Returns the username if valid, otherwise throws an authentication error.
    """
    try:
        payload = jwt.decode(token, token_settings.secret_key, algorithms=[token_settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
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


@app.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    user_convos = get_user_conversations(db, current_user.id)

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


@app.get("/conversations/{thread_id}", response_model=ConversationResponse)
async def get_conversation(
        thread_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Check if conversation exists and user has access
    convo = get_one_conversation(db, thread_id)
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


@app.get("/conversations/{thread_id}/stream")
async def stream_messages(
        query: str,
        thread_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Check if conversation exists and user has access
    convo = get_one_conversation(db, thread_id)
    if convo:
        if convo.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    async def stream_generator() -> AsyncGenerator[str, None]:
        try:
            # Use the RAG streaming function
            for token in rag.stream(query=query, thread_id=thread_id):
                # Just yield the token directly
                yield token

        except Exception as e:
            print(f"Error in streaming: {str(e)}")
            yield f"ERROR: {str(e)}"

    # Return a StreamingResponse with plain text content type
    return StreamingResponse(
        stream_generator(),
        media_type="text/plain"
    )


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
