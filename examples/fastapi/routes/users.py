"""User CRUD endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from surrealdb import AsyncSurreal

from database import get_db
from models import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: AsyncSurreal = Depends(get_db),
) -> UserResponse:
    """Create a new user."""
    try:
        result = await db.create(
            "users",
            {
                "name": user.name,
                "email": user.email,
                "age": user.age,
            },
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return UserResponse(
            id=str(user_data.get("id", "")),
            name=user_data["name"],
            email=user_data["email"],
            age=user_data.get("age"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSurreal = Depends(get_db),
) -> List[UserResponse]:
    """Get all users."""
    try:
        result = await db.select("users")

        if not result:
            return []

        users = []
        for user_data in result:
            users.append(
                UserResponse(
                    id=str(user_data.get("id", "")),
                    name=user_data["name"],
                    email=user_data["email"],
                    age=user_data.get("age"),
                )
            )

        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSurreal = Depends(get_db),
) -> UserResponse:
    """Get a user by ID."""
    try:
        result = await db.select(user_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return UserResponse(
            id=str(user_data.get("id", "")),
            name=user_data["name"],
            email=user_data["email"],
            age=user_data.get("age"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user: UserUpdate,
    db: AsyncSurreal = Depends(get_db),
) -> UserResponse:
    """Update a user."""
    try:
        # Build update data, excluding None values
        update_data = {}
        if user.name is not None:
            update_data["name"] = user.name
        if user.email is not None:
            update_data["email"] = user.email
        if user.age is not None:
            update_data["age"] = user.age

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )

        result = await db.merge(user_id, update_data)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return UserResponse(
            id=str(user_data.get("id", "")),
            name=user_data["name"],
            email=user_data["email"],
            age=user_data.get("age"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSurreal = Depends(get_db),
) -> None:
    """Delete a user."""
    try:
        result = await db.delete(user_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
