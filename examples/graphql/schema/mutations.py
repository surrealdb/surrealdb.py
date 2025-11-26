"""GraphQL mutation resolvers."""

from typing import Optional

import strawberry
from strawberry.types import Info

from database import db_manager

from .types import AuthResponse, User


@strawberry.type
class Mutation:
    """Root Mutation type."""

    @strawberry.mutation
    async def create_user(
        self,
        info: Info,
        name: str,
        email: str,
        age: Optional[int] = None,
    ) -> User:
        """Create a new user.

        Args:
            name: The user's name
            email: The user's email
            age: The user's age (optional)

        Returns:
            The created user
        """
        db = db_manager.get_db()

        try:
            result = await db.create(
                "users",
                {
                    "name": name,
                    "email": email,
                    "age": age,
                },
            )

            if not result:
                raise Exception("Failed to create user")

            user_data = result[0] if isinstance(result, list) else result

            return User(
                id=str(user_data.get("id", "")),
                name=user_data["name"],
                email=user_data["email"],
                age=user_data.get("age"),
            )
        except Exception as e:
            raise Exception(f"Failed to create user: {str(e)}")

    @strawberry.mutation
    async def update_user(
        self,
        info: Info,
        id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        age: Optional[int] = None,
    ) -> User:
        """Update an existing user.

        Args:
            id: The user's ID
            name: New name (optional)
            email: New email (optional)
            age: New age (optional)

        Returns:
            The updated user
        """
        db = db_manager.get_db()

        try:
            # Build update data
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if email is not None:
                update_data["email"] = email
            if age is not None:
                update_data["age"] = age

            if not update_data:
                raise Exception("No fields to update")

            result = await db.merge(id, update_data)

            if not result:
                raise Exception(f"User {id} not found")

            user_data = result[0] if isinstance(result, list) else result

            return User(
                id=str(user_data.get("id", "")),
                name=user_data["name"],
                email=user_data["email"],
                age=user_data.get("age"),
            )
        except Exception as e:
            raise Exception(f"Failed to update user: {str(e)}")

    @strawberry.mutation
    async def delete_user(self, info: Info, id: str) -> bool:
        """Delete a user.

        Args:
            id: The user's ID

        Returns:
            True if deleted successfully
        """
        db = db_manager.get_db()

        try:
            result = await db.delete(id)

            if not result:
                raise Exception(f"User {id} not found")

            return True
        except Exception as e:
            raise Exception(f"Failed to delete user: {str(e)}")

    @strawberry.mutation
    async def signup(
        self,
        info: Info,
        namespace: str,
        database: str,
        access: str,
        email: str,
        password: str,
    ) -> AuthResponse:
        """Register a new user account.

        Args:
            namespace: SurrealDB namespace
            database: SurrealDB database
            access: Access level
            email: User email
            password: User password

        Returns:
            Authentication response with token
        """
        db = db_manager.get_db()

        try:
            token = await db.signup(
                {
                    "namespace": namespace,
                    "database": database,
                    "access": access,
                    "email": email,
                    "password": password,
                }
            )

            return AuthResponse(
                token=token,
                message="User registered successfully",
            )
        except Exception as e:
            raise Exception(f"Signup failed: {str(e)}")

    @strawberry.mutation
    async def signin(
        self,
        info: Info,
        username: str,
        password: str,
    ) -> AuthResponse:
        """Sign in to an account.

        Args:
            username: Username
            password: Password

        Returns:
            Authentication response with token
        """
        db = db_manager.get_db()

        try:
            token = await db.signin(
                {
                    "username": username,
                    "password": password,
                }
            )

            return AuthResponse(
                token=token,
                message="Signed in successfully",
            )
        except Exception as e:
            raise Exception(f"Authentication failed: {str(e)}")
