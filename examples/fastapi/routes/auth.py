"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from surrealdb import AsyncSurreal

from database import get_db
from models import AuthResponse, MessageResponse, SigninRequest, SignupRequest

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    db: AsyncSurreal = Depends(get_db),
) -> AuthResponse:
    """Register a new user account."""
    try:
        token = await db.signup(
            {
                "namespace": request.namespace,
                "database": request.database,
                "access": request.access,
                "email": request.email,
                "password": request.password,
            }
        )

        return AuthResponse(
            token=token,
            message="User registered successfully",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signup failed: {str(e)}",
        )


@router.post("/signin", response_model=AuthResponse)
async def signin(
    request: SigninRequest,
    db: AsyncSurreal = Depends(get_db),
) -> AuthResponse:
    """Sign in to an account."""
    try:
        token = await db.signin(
            {
                "username": request.username,
                "password": request.password,
            }
        )

        return AuthResponse(
            token=token,
            message="Signed in successfully",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


@router.post("/invalidate", response_model=MessageResponse)
async def invalidate(
    db: AsyncSurreal = Depends(get_db),
) -> MessageResponse:
    """Sign out and invalidate the session."""
    try:
        await db.invalidate()
        return MessageResponse(message="Session invalidated successfully")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalidation failed: {str(e)}",
        )
