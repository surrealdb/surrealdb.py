"""User CRUD endpoints."""

from typing import List

from litestar import Controller, delete, get, post, put
from litestar.di import Provide
from litestar.exceptions import InternalServerException, NotFoundException
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from surrealdb import AsyncSurreal

from database import provide_db
from models import (
    UserCreate,
    UserCreateDTO,
    UserResponse,
    UserResponseDTO,
    UserUpdate,
    UserUpdateDTO,
)


class UserController(Controller):
    """User CRUD controller."""

    path = "/users"
    dependencies = {"db": Provide(provide_db)}

    @post(dto=UserCreateDTO, return_dto=UserResponseDTO, status_code=HTTP_201_CREATED)
    async def create_user(self, data: UserCreate, db: AsyncSurreal) -> UserResponse:
        """Create a new user."""
        try:
            result = await db.create(
                "users",
                {
                    "name": data.name,
                    "email": data.email,
                    "age": data.age,
                },
            )

            if not result:
                raise InternalServerException("Failed to create user")

            # Handle both list and dict responses
            user_data = result[0] if isinstance(result, list) else result

            return UserResponse(
                id=str(user_data.get("id", "")),
                name=user_data["name"],
                email=user_data["email"],
                age=user_data.get("age"),
            )
        except Exception as e:
            raise InternalServerException(f"Database error: {str(e)}")

    @get(return_dto=UserResponseDTO)
    async def list_users(self, db: AsyncSurreal) -> List[UserResponse]:
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
            raise InternalServerException(f"Database error: {str(e)}")

    @get("/{user_id:str}", return_dto=UserResponseDTO)
    async def get_user(self, user_id: str, db: AsyncSurreal) -> UserResponse:
        """Get a user by ID."""
        try:
            result = await db.select(user_id)

            if not result:
                raise NotFoundException(f"User {user_id} not found")

            # Handle both list and dict responses
            user_data = result[0] if isinstance(result, list) else result

            return UserResponse(
                id=str(user_data.get("id", "")),
                name=user_data["name"],
                email=user_data["email"],
                age=user_data.get("age"),
            )
        except NotFoundException:
            raise
        except Exception as e:
            raise InternalServerException(f"Database error: {str(e)}")

    @put("/{user_id:str}", dto=UserUpdateDTO, return_dto=UserResponseDTO)
    async def update_user(
        self,
        user_id: str,
        data: UserUpdate,
        db: AsyncSurreal,
    ) -> UserResponse:
        """Update a user."""
        try:
            # Build update data, excluding None values
            update_data = {}
            if data.name is not None:
                update_data["name"] = data.name
            if data.email is not None:
                update_data["email"] = data.email
            if data.age is not None:
                update_data["age"] = data.age

            if not update_data:
                raise InternalServerException("No fields to update")

            result = await db.merge(user_id, update_data)

            if not result:
                raise NotFoundException(f"User {user_id} not found")

            # Handle both list and dict responses
            user_data = result[0] if isinstance(result, list) else result

            return UserResponse(
                id=str(user_data.get("id", "")),
                name=user_data["name"],
                email=user_data["email"],
                age=user_data.get("age"),
            )
        except NotFoundException:
            raise
        except Exception as e:
            raise InternalServerException(f"Database error: {str(e)}")

    @delete("/{user_id:str}", status_code=HTTP_204_NO_CONTENT)
    async def delete_user(self, user_id: str, db: AsyncSurreal) -> None:
        """Delete a user."""
        try:
            result = await db.delete(user_id)

            if not result:
                raise NotFoundException(f"User {user_id} not found")
        except NotFoundException:
            raise
        except Exception as e:
            raise InternalServerException(f"Database error: {str(e)}")
