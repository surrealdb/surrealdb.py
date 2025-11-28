"""Database connection management."""

from typing import AsyncGenerator

from surrealdb import AsyncSurreal

from config import settings


class DatabaseManager:
    """Manages SurrealDB connections."""

    def __init__(self):
        self.db: AsyncSurreal | None = None

    async def connect(self) -> None:
        """Initialize database connection."""
        self.db = AsyncSurreal(settings.surrealdb_url)
        await self.db.connect()
        await self.db.signin(
            {
                "username": settings.surrealdb_username,
                "password": settings.surrealdb_password,
            }
        )
        await self.db.use(settings.surrealdb_namespace, settings.surrealdb_database)

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


async def provide_db() -> AsyncGenerator[AsyncSurreal, None]:
    """Dependency provider for database connection."""
    yield db_manager.get_db()
