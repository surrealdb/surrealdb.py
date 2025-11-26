"""DTOs and data models."""

from dataclasses import dataclass
from typing import Optional

from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig


@dataclass
class UserCreate:
    """DTO for creating a new user."""

    name: str
    email: str
    age: Optional[int] = None


@dataclass
class UserUpdate:
    """DTO for updating a user."""

    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None


@dataclass
class UserResponse:
    """DTO for user response."""

    id: str
    name: str
    email: str
    age: Optional[int] = None


@dataclass
class SignupRequest:
    """DTO for user signup."""

    namespace: str
    database: str
    access: str
    email: str
    password: str


@dataclass
class SigninRequest:
    """DTO for user signin."""

    username: str
    password: str


@dataclass
class AuthResponse:
    """DTO for authentication response."""

    token: str
    message: str


@dataclass
class MessageResponse:
    """Generic message response."""

    message: str


# DTO configurations
class UserCreateDTO(DataclassDTO[UserCreate]):
    """DTO for UserCreate."""

    config = DTOConfig()


class UserUpdateDTO(DataclassDTO[UserUpdate]):
    """DTO for UserUpdate."""

    config = DTOConfig(partial=True)


class UserResponseDTO(DataclassDTO[UserResponse]):
    """DTO for UserResponse."""

    config = DTOConfig()
