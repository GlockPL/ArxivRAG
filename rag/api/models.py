from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict

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