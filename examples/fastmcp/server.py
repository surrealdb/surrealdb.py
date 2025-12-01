"""FastMCP + SurrealDB Server.

This MCP server provides tools and resources for interacting with SurrealDB,
allowing AI assistants like Claude to perform database operations.
"""


from fastmcp import FastMCP

from database import db_manager
from resources import get_db_config, get_db_schema
from tools import (
    create_user,
    delete_user,
    execute_query,
    get_user,
    list_users,
    update_user,
)

# Create MCP server
mcp = FastMCP("SurrealDB MCP Server")


# Lifecycle hooks
@mcp.on_startup
async def startup():
    """Initialize database connection on startup."""
    await db_manager.connect()


@mcp.on_shutdown
async def shutdown():
    """Close database connection on shutdown."""
    await db_manager.disconnect()


# Register tools
@mcp.tool()
async def mcp_create_user(name: str, email: str, age: int | None = None):
    """Create a new user in the database."""
    return await create_user(name, email, age)


@mcp.tool()
async def mcp_list_users():
    """List all users in the database."""
    return await list_users()


@mcp.tool()
async def mcp_get_user(user_id: str):
    """Get a specific user by ID."""
    return await get_user(user_id)


@mcp.tool()
async def mcp_update_user(
    user_id: str,
    name: str | None = None,
    email: str | None = None,
    age: int | None = None,
):
    """Update a user's information."""
    return await update_user(user_id, name, email, age)


@mcp.tool()
async def mcp_delete_user(user_id: str):
    """Delete a user from the database."""
    return await delete_user(user_id)


@mcp.tool()
async def mcp_execute_query(query: str):
    """Execute a custom SurrealQL query."""
    return await execute_query(query)


# Register resources
@mcp.resource("surrealdb://config")
async def db_config():
    """Get database configuration information."""
    return await get_db_config()


@mcp.resource("surrealdb://schema")
async def db_schema():
    """Get database schema information."""
    return await get_db_schema()


# Run the server
if __name__ == "__main__":
    # Run with stdio transport (for Claude Desktop)
    mcp.run()
