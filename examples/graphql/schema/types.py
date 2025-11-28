"""GraphQL type definitions."""

from typing import Optional

import strawberry


@strawberry.type
class User:
    """User type representing a user in the system."""

    id: str
    name: str
    email: str
    age: Optional[int] = None


@strawberry.type
class AuthResponse:
    """Authentication response type."""

    token: str
    message: str
