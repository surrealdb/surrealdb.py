"""DataLoader implementation for batching and caching."""

from typing import List, Optional

from strawberry.dataloader import DataLoader
from surrealdb import AsyncSurreal


class UserDataLoader(DataLoader):
    """DataLoader for batching user queries."""

    def __init__(self, db: AsyncSurreal):
        super().__init__(load_fn=self.load_users)
        self.db = db

    async def load_users(self, keys: List[str]) -> List[Optional[dict]]:
        """Batch load users by IDs.

        This prevents N+1 query problems by loading multiple users
        in a single database query.
        """
        if not keys:
            return []

        try:
            # Fetch all requested users in one query
            results = []
            for user_id in keys:
                result = await self.db.select(user_id)
                if result:
                    user_data = result[0] if isinstance(result, list) else result
                    results.append(user_data)
                else:
                    results.append(None)

            return results
        except Exception:
            # Return None for each key if query fails
            return [None] * len(keys)
