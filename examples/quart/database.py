"""Database connection management."""

from quart import current_app, g
from surrealdb import AsyncSurreal


async def get_db() -> AsyncSurreal:
    """Get database connection for current request.

    Creates a new connection if one doesn't exist in the request context.
    """
    if "db" not in g:
        db = AsyncSurreal(current_app.config["SURREALDB_URL"])
        await db.connect()
        await db.signin(
            {
                "username": current_app.config["SURREALDB_USERNAME"],
                "password": current_app.config["SURREALDB_PASSWORD"],
            }
        )
        await db.use(
            current_app.config["SURREALDB_NAMESPACE"],
            current_app.config["SURREALDB_DATABASE"],
        )
        g.db = db

    return g.db


async def close_db(e=None) -> None:
    """Close database connection at end of request."""
    db = g.pop("db", None)

    if db is not None:
        await db.close()


def init_app(app) -> None:
    """Initialize database with Quart app."""
    app.teardown_appcontext(close_db)
