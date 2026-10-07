"""DTOs and data models."""

from dataclasses import dataclass

from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig


@dataclass
class UserCreate:
    """DTO for creating a new user."""

    name: str
    email: str
    age: int | None = None


@dataclass
class UserUpdate:
    """DTO for updating a user."""

    name: str | None = None
    email: str | None = None
    age: int | None = None


@dataclass
class UserResponse:
    """DTO for user response."""

    id: str
    name: str
    email: str
    age: int | None = None


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
