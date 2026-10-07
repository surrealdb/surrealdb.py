"""GraphQL type definitions."""

import strawberry


@strawberry.type
class User:
    """User type representing a user in the system."""

    id: str
    name: str
    email: str
    age: int | None = None


@strawberry.type
class AuthResponse:
    """Authentication response type."""

    token: str
    message: str
