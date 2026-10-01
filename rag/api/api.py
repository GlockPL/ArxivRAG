"""
Api file with routs
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, AsyncGenerator, Optional
from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI, Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langchain_core.messages import HumanMessage, AIMessage
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from rag.api.models import MessageResponse, TokenData, UserResponse, UserCreate, \
    Token, ConversationResponse, RefreshRequest, ChatRequest
from rag.api.utils import get_password_hash, authenticate_user, create_access_token, \
    create_refresh_token, store_refresh_token, is_token_blacklisted, validate_refresh_token, \
    invalidate_refresh_token, logout_operation, invalidate_all_user_tokens, \
    get_user_conversation_newest, get_user_conversation_count, get_user_conversations, \
    get_one_conversation, generate_thread_id, get_conversation_with_check
from rag.settings import db_settings, token_settings, host_settings
from rag.db.db_objects import User, LoginHistory, Base, ConversationTitle
from rag.rag_pipeline import RAG

engine = create_async_engine(db_settings.uri("postgresql+asyncpg"), echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup: create tables and open the connections used by the RAG pipeline before serving requests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application.state.rag = await RAG.create()

    yield  # This is where FastAPI serves requests

    # Shutdown: cleanup resources
    await application.state.rag.close()
    await engine.dispose()


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Chat API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_db():
    """
    Dependency to get the database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_rag(request: Request) -> RAG:
    """
    Dependency to get the RAG pipeline created at startup
    """
    return request.app.state.rag


async def get_messages(rag: RAG, thread_id: str) -> List[MessageResponse]:
    """
    Return all ai/human messages for a chat conversation defined by thread_id
    """
    messages_list = []
    for message in await rag.get_messages(thread_id):
        if isinstance(message, HumanMessage):
            msg_type = "human"
        elif isinstance(message, AIMessage):
            msg_type = "ai"
        else:
            continue

        if not message.text:
            continue

        messages_list.append(MessageResponse(content=message.text, type=msg_type, thread_id=thread_id))

    return messages_list


async def get_current_user(db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)):
    """
    Return current logged in user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if await is_token_blacklisted(token):
        raise credentials_exception

    try:
        payload = jwt.decode(token, token_settings.secret_key, algorithms=[token_settings.algorithm])
        username: str = payload.get("sub")
        if username is None or payload.get("token_type") != "access":
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError as jwt_error:
        raise credentials_exception from jwt_error

    result = await db.execute(select(User).filter(User.username == token_data.username))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user


# ----- API Endpoints -----
@app.post("/register", response_model=UserResponse)
@limiter.limit("4/hour")
async def register_user(user: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    # Check if username exists
    result = await db.execute(select(User).filter(User.username == user.username))
    db_user = result.scalars().first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Check if email exists
    result = await db.execute(select(User).filter(User.email == user.email))
    db_user = result.scalars().first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    hashed_password = await get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        name=user.name,
        password=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@app.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(
        request: Request,
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, form_data.username, form_data.password)
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
    await db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=token_settings.token_expires_minutes)
    access_token = await create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Create refresh token
    refresh_token_expires = timedelta(days=token_settings.refresh_token_expires_days)
    refresh_token, expire_time = await create_refresh_token(
        data={"sub": user.username},
        expires_delta=refresh_token_expires
    )

    # Store refresh token in Redis
    token_expires_seconds = int(refresh_token_expires.total_seconds())
    await store_refresh_token(user.id, refresh_token, token_expires_seconds)

    return Token(access_token=access_token, refresh_token=refresh_token, token_type="Bearer")


@app.post("/refresh", response_model=Token)
@limiter.limit("3/hour")
async def refresh_access_token(
        request: Request,
        refresh_data: RefreshRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for refreshing an access token through refresh token
    It also blacklists current refresh token and generates a new one
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    refresh_token = refresh_data.refresh_token

    # Check if token is blacklisted
    if await is_token_blacklisted(refresh_token):
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
        result = await db.execute(select(User).filter(User.username == username))
        user = result.scalars().first()
        if user is None:
            raise credentials_exception

        # Validate token exists in Redis
        user_id = await validate_refresh_token(refresh_token)
        if user_id is None or user_id != user.id:
            raise credentials_exception

        # Invalidate the used refresh token (one-time use)
        await invalidate_refresh_token(refresh_token)

        # Create new access token
        access_token_expires = timedelta(minutes=token_settings.token_expires_minutes)
        new_access_token = await create_access_token(
            data={"sub": username},
            expires_delta=access_token_expires
        )

        # Create new refresh token
        refresh_token_expires = timedelta(days=token_settings.refresh_token_expires_days)
        new_refresh_token, expire_time = await create_refresh_token(
            data={"sub": username},
            expires_delta=refresh_token_expires
        )

        # Store new refresh token
        token_expires_seconds = int(refresh_token_expires.total_seconds())
        await store_refresh_token(user.id, new_refresh_token, token_expires_seconds)

        return Token(access_token=new_access_token, refresh_token=new_refresh_token, token_type="Bearer")

    except JWTError as jwt_error:
        raise credentials_exception from jwt_error


@app.post("/logout")
@limiter.limit("15/hour")
async def logout(
        request: Request,
        refresh_data: Optional[RefreshRequest] = None,
):
    await logout_operation(request)

    # Invalidate refresh token if provided in the request body
    if refresh_data:
        await invalidate_refresh_token(refresh_data.refresh_token)

    return {"detail": "Successfully logged out"}


@app.post("/logout-all")
@limiter.limit("10/hour")
async def logout_all_devices(
        request: Request,
        current_user: User = Depends(get_current_user)
):
    """
    Logout all devices.
    """
    await logout_operation(request)
    # Invalidate all refresh tokens for user
    await invalidate_all_user_tokens(current_user.id)

    return {"detail": "Successfully logged out from all devices"}


@app.post("/validate-token")
@limiter.limit("30/minute")
async def validate_token(request: Request, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Validates if a token is valid and not expired.
    This endpoint accepts the token via the Authorization header.
    Returns the username if valid, otherwise throws an authentication error.
    """
    # Check if token is blacklisted
    if await is_token_blacklisted(token):
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

        result = await db.execute(select(User).filter(User.username == username))
        user = result.scalars().first()
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


    except JWTError as jwt_error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        ) from jwt_error


@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/conversation/newest", response_model=ConversationResponse)
async def get_newest_conversation(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    convo = await get_user_conversation_newest(db, current_user.id)
    return convo


@app.get("/conversations/count", response_model=dict)
async def count_conversations(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    count = await get_user_conversation_count(db, current_user.id)
    return {"total": count}


@app.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
        limit: int = Query(10, ge=1, le=100, description="Number of conversations to return"),
        offset: int = Query(0, ge=0, description="Number of conversations to skip"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user_convos = await get_user_conversations(db, current_user.id, limit, offset)

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


async def stream_generator(rag: RAG, query: str, thread_id: str,
                           title_task: Optional[asyncio.Task]) -> AsyncGenerator[str, None]:
    """
    Stream the answer as server-sent events. For a new conversation, title_task generates its title
    concurrently with the answer, and the title is saved and sent in the final event.
    """
    def event(event_type: str, content: str) -> str:
        return f"data: {json.dumps({'type': event_type, 'content': content, 'thread_id': thread_id})}\n\n"

    yield event("connection_established", "[START]")
    try:
        async for token in rag.astream(query=query, thread_id=thread_id):
            yield event("message", token)

        title = ""
        if title_task:
            try:
                title = await title_task
            except Exception:
                logging.exception("Error generating conversation title")
                title = query[:50]
            # The request's database session is closed once streaming starts, so use a new one
            async with AsyncSessionLocal() as db:
                convo = await get_one_conversation(db, thread_id)
                convo.title = title
                await db.commit()

        yield event("streaming_finished", title)

    except Exception as e:
        logging.exception("Error in streaming")
        yield event("error", str(e))

    finally:
        # Stop the title request if the answer failed or the client disconnected
        if title_task and not title_task.done():
            title_task.cancel()


@app.post("/conversations/stream")
async def stream_messages(
        chat: ChatRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        rag: RAG = Depends(get_rag),
):
    """
    Send a message and stream the answer. Without a known thread_id a new conversation is created.
    """
    convo = await get_one_conversation(db, chat.thread_id) if chat.thread_id else None
    if convo and convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    title_task = None
    if convo:
        thread_id = convo.thread_id
    else:
        # Register the conversation before answering, so it belongs to the user even if the answer fails
        thread_id = generate_thread_id()
        db.add(ConversationTitle(thread_id=thread_id, title="New chat", created_at=datetime.now(),
                                 user_id=current_user.id))
        await db.commit()
        title_task = asyncio.create_task(rag.generate_title(chat.query))

    headers = {
        "X-Thread-ID": thread_id,
        "Access-Control-Expose-Headers": "X-Thread-ID",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    return StreamingResponse(
        stream_generator(rag, chat.query, thread_id, title_task),
        media_type="text/event-stream",
        headers=headers
    )


@app.get("/conversations/{thread_id}", response_model=ConversationResponse)
async def get_conversation(
        thread_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """

    """
    # Check if conversation exists and user has access
    convo = await get_one_conversation(db, thread_id)
    logging.info("I'm in conversation %s", thread_id)
    conv_response = await get_conversation_with_check(convo, current_user)
    return conv_response


@app.get("/conversations/{thread_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
        thread_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        rag: RAG = Depends(get_rag),
) -> List[MessageResponse]:
    """
    Return all messages for a conversation.
    """
    # Check if conversation exists and user has access
    convo = await get_one_conversation(db, thread_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    # Get messages
    messages = await get_messages(rag, thread_id)
    return messages


@app.put("/conversations/{thread_id}", response_model=ConversationResponse)
async def update_conversation_title(
        thread_id: str,
        title: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Modify conversation title
    """
    # Check if conversation exists and user has access
    convo = await get_one_conversation(db, thread_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if user owns the conversation
    if convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this conversation")

    # Update the title
    convo.title = title
    await db.commit()
    await db.refresh(convo)

    return convo


@app.delete("/conversations/{thread_id}", response_model=dict)
async def delete_conversation(
        thread_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        rag: RAG = Depends(get_rag),
):
    """
    Delete a conversation with its message history
    """
    # Check if conversation exists and user has access
    convo = await get_one_conversation(db, thread_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if user owns the conversation
    if convo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this conversation")

    # Delete the message history saved by the LangGraph checkpointer
    await rag.delete_thread(thread_id)

    # Finally delete the conversation itself
    await db.delete(convo)

    # Commit all changes
    await db.commit()

    return {"message": f"Conversation {thread_id} and all associated checkpoints deleted successfully"}


frontend_path = Path('./rag/web/arxiv_ai_chat/dist')
app.mount("/assets", StaticFiles(directory=frontend_path / "assets"), name="assets")


# Serve other static files directly if they exist
@app.get("/favicon.ico")
async def favicon():
    """
    Return favicon image
    """
    return FileResponse(frontend_path / "favicon.ico")


@app.get("/{full_path:path}")
async def serve_spa():
    """
    Catch-all route to return index.html for SPA routing
    Otherwise return index.html for SPA routing
    """
    return FileResponse(frontend_path / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
