"""
Models for fast api routes
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


# ----- Pydantic Models for API -----

class UserBase(BaseModel):
    """
    Model for a user
    """
    username: str
    email: EmailStr
    name: str


class UserCreate(UserBase):
    """
    This model additionally has password that is used during registration
    """
    password: str


class UserResponse(UserBase):
    """
    This model is based on database version of user
    """
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenData(BaseModel):
    """
    Data returned by during token authentication
    """
    username: Optional[str] = None
    token_type: Optional[str] = None


class Token(BaseModel):
    """
    Return type for created tokens
    """
    access_token: str
    refresh_token: str
    token_type: str


class MessageResponse(BaseModel):
    """
    Model for a message response where
    type is either AI or Human
    """
    content: str
    type: str
    thread_id: str


class ConversationResponse(BaseModel):
    """
    Model for a conversation response, based on db table conversation_titles
    """
    thread_id: str
    title: str
    created_at: datetime
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class RefreshRequest(BaseModel):
    """
    Model for a refresh request
    """
    refresh_token: str
