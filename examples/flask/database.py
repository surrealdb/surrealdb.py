"""Database connection management."""

from flask import current_app, g
from surrealdb import Surreal


def get_db() -> Surreal:
    """Get database connection for current request.

    Creates a new connection if one doesn't exist in the request context.
    """
    if "db" not in g:
        db = Surreal(current_app.config["SURREALDB_URL"])
        db.connect()
        db.signin(
            {
                "username": current_app.config["SURREALDB_USERNAME"],
                "password": current_app.config["SURREALDB_PASSWORD"],
            }
        )
        db.use(
            current_app.config["SURREALDB_NAMESPACE"],
            current_app.config["SURREALDB_DATABASE"],
        )
        g.db = db

    return g.db


def close_db(e=None) -> None:
    """Close database connection at end of request."""
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_app(app) -> None:
    """Initialize database with Flask app."""
    app.teardown_appcontext(close_db)
