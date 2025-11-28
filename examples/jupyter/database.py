"""Database connection helper for notebooks."""

from surrealdb import AsyncSurreal

from config import settings


async def get_connection() -> AsyncSurreal:
    """Get a connected SurrealDB instance.

    Returns:
        Connected AsyncSurreal client

    Example:
        ```python
        db = await get_connection()
        result = await db.select("users")
        ```
    """
    db = AsyncSurreal(settings.surrealdb_url)
    await db.connect()
    await db.signin(
        {
            "username": settings.surrealdb_username,
            "password": settings.surrealdb_password,
        }
    )
    await db.use(settings.surrealdb_namespace, settings.surrealdb_database)
    return db


async def close_connection(db: AsyncSurreal) -> None:
    """Close database connection.

    Args:
        db: The database connection to close
    """
    if db:
        await db.close()
