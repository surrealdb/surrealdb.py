"""Database connection management."""

from surrealdb import AsyncSurreal

from config import config


class DatabaseManager:
    """Manages SurrealDB connections."""

    def __init__(self):
        self.db: AsyncSurreal | None = None

    async def connect(self) -> None:
        """Initialize database connection."""
        self.db = AsyncSurreal(config.SURREALDB_URL)
        await self.db.connect()
        await self.db.signin(
            {
                "username": config.SURREALDB_USERNAME,
                "password": config.SURREALDB_PASSWORD,
            }
        )
        await self.db.use(config.SURREALDB_NAMESPACE, config.SURREALDB_DATABASE)

    async def disconnect(self) -> None:
        """Close database connection."""
        if self.db:
            await self.db.close()
            self.db = None

    def get_db(self) -> AsyncSurreal:
        """Get the database connection."""
        if not self.db:
            raise RuntimeError("Database not connected")
        return self.db


# Global database manager instance
db_manager = DatabaseManager()
