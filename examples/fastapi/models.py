"""Pydantic models for request/response validation."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Model for creating a new user."""

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    age: Optional[int] = Field(None, ge=0, le=150)


class UserUpdate(BaseModel):
    """Model for updating a user."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(None, ge=0, le=150)


class UserResponse(BaseModel):
    """Model for user response."""

    id: str
    name: str
    email: str
    age: Optional[int] = None

    model_config = {"from_attributes": True}


class SignupRequest(BaseModel):
    """Model for user signup."""

    namespace: str
    database: str
    access: str
    email: EmailStr
    password: str = Field(..., min_length=8)


class SigninRequest(BaseModel):
    """Model for user signin."""

    username: str
    password: str


class AuthResponse(BaseModel):
    """Model for authentication response."""

    token: str
    message: str


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
