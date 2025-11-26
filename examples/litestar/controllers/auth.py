"""Authentication endpoints."""

from litestar import Controller, post
from litestar.di import Provide
from litestar.exceptions import InternalServerException
from litestar.status_codes import HTTP_201_CREATED
from surrealdb import AsyncSurreal

from database import provide_db
from models import AuthResponse, MessageResponse, SigninRequest, SignupRequest


class AuthController(Controller):
    """Authentication controller."""

    path = "/auth"
    dependencies = {"db": Provide(provide_db)}

    @post("/signup", status_code=HTTP_201_CREATED)
    async def signup(self, data: SignupRequest, db: AsyncSurreal) -> AuthResponse:
        """Register a new user account."""
        try:
            token = await db.signup(
                {
                    "namespace": data.namespace,
                    "database": data.database,
                    "access": data.access,
                    "email": data.email,
                    "password": data.password,
                }
            )

            return AuthResponse(
                token=token,
                message="User registered successfully",
            )
        except Exception as e:
            raise InternalServerException(f"Signup failed: {str(e)}")

    @post("/signin")
    async def signin(self, data: SigninRequest, db: AsyncSurreal) -> AuthResponse:
        """Sign in to an account."""
        try:
            token = await db.signin(
                {
                    "username": data.username,
                    "password": data.password,
                }
            )

            return AuthResponse(
                token=token,
                message="Signed in successfully",
            )
        except Exception as e:
            raise InternalServerException(f"Authentication failed: {str(e)}")

    @post("/invalidate")
    async def invalidate(self, db: AsyncSurreal) -> MessageResponse:
        """Sign out and invalidate the session."""
        try:
            await db.invalidate()
            return MessageResponse(message="Session invalidated successfully")
        except Exception as e:
            raise InternalServerException(f"Invalidation failed: {str(e)}")
