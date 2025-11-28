"""GraphQL query resolvers."""

from typing import List, Optional

import strawberry
from strawberry.types import Info

from database import db_manager

from .types import User


@strawberry.type
class Query:
    """Root Query type."""

    @strawberry.field
    async def users(self, info: Info) -> List[User]:
        """Get all users.

        Returns:
            List of all users in the database
        """
        db = db_manager.get_db()

        try:
            result = await db.select("users")

            if not result:
                return []

            users = []
            for user_data in result:
                users.append(
                    User(
                        id=str(user_data.get("id", "")),
                        name=user_data["name"],
                        email=user_data["email"],
                        age=user_data.get("age"),
                    )
                )

            return users
        except Exception as e:
            raise Exception(f"Failed to fetch users: {str(e)}")

    @strawberry.field
    async def user(self, info: Info, id: str) -> Optional[User]:
        """Get a single user by ID.

        Args:
            id: The user's ID

        Returns:
            User if found, None otherwise
        """
        db = db_manager.get_db()

        try:
            result = await db.select(id)

            if not result:
                return None

            user_data = result[0] if isinstance(result, list) else result

            return User(
                id=str(user_data.get("id", "")),
                name=user_data["name"],
                email=user_data["email"],
                age=user_data.get("age"),
            )
        except Exception as e:
            raise Exception(f"Failed to fetch user {id}: {str(e)}")
