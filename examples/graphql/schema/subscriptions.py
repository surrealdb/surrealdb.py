"""GraphQL subscription resolvers."""

from typing import AsyncGenerator

import strawberry
from strawberry.types import Info

from database import db_manager

from .types import User


@strawberry.type
class Subscription:
    """Root Subscription type."""

    @strawberry.subscription
    async def user_updated(self, info: Info) -> AsyncGenerator[User, None]:
        """Subscribe to user updates.

        Yields:
            User objects as they are created, updated, or deleted
        """
        db = db_manager.get_db()

        try:
            # Subscribe to live queries on the users table
            live_query_id = await db.live("users")

            # Stream updates to subscribers
            async for result in db.subscribe_live(live_query_id):
                # Parse the live query result
                if isinstance(result, dict) and "result" in result:
                    user_data = result["result"]

                    yield User(
                        id=str(user_data.get("id", "")),
                        name=user_data.get("name", ""),
                        email=user_data.get("email", ""),
                        age=user_data.get("age"),
                    )
        except Exception as e:
            # Log error but don't break the subscription
            print(f"Subscription error: {e}")
