"""MCP resource handlers for SurrealDB."""

from config import settings


async def get_db_config() -> dict:
    """Get database configuration information.

    Returns:
        Database connection configuration
    """
    return {
        "url": settings.surrealdb_url,
        "namespace": settings.surrealdb_namespace,
        "database": settings.surrealdb_database,
        "connected": True,
    }


async def get_db_schema() -> dict:
    """Get database schema information.

    Returns:
        Database schema details
    """
    # This is a placeholder - you would implement actual schema introspection
    return {
        "tables": [
            {
                "name": "users",
                "fields": [
                    {"name": "id", "type": "record"},
                    {"name": "name", "type": "string"},
                    {"name": "email", "type": "string"},
                    {"name": "age", "type": "int"},
                ],
            }
        ],
    }
