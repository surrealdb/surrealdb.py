"""MCP tool definitions for SurrealDB operations."""

from typing import Optional

from database import db_manager


async def create_user(name: str, email: str, age: Optional[int] = None) -> dict:
    """Create a new user in the database.

    Args:
        name: The user's full name
        email: The user's email address
        age: The user's age (optional)

    Returns:
        The created user object with ID
    """
    try:
        db = db_manager.get_db()
        result = await db.create(
            "users",
            {
                "name": name,
                "email": email,
                "age": age,
            },
        )

        if not result:
            return {"error": "Failed to create user"}

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return {
            "id": str(user_data.get("id", "")),
            "name": user_data["name"],
            "email": user_data["email"],
            "age": user_data.get("age"),
        }
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def list_users() -> dict:
    """List all users in the database.

    Returns:
        A list of all user objects
    """
    try:
        db = db_manager.get_db()
        result = await db.select("users")

        if not result:
            return {"users": []}

        users = []
        for user_data in result:
            users.append(
                {
                    "id": str(user_data.get("id", "")),
                    "name": user_data["name"],
                    "email": user_data["email"],
                    "age": user_data.get("age"),
                }
            )

        return {"users": users, "count": len(users)}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def get_user(user_id: str) -> dict:
    """Get a specific user by ID.

    Args:
        user_id: The user's ID (e.g., 'users:johndoe')

    Returns:
        The user object
    """
    try:
        db = db_manager.get_db()
        result = await db.select(user_id)

        if not result:
            return {"error": f"User {user_id} not found"}

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return {
            "id": str(user_data.get("id", "")),
            "name": user_data["name"],
            "email": user_data["email"],
            "age": user_data.get("age"),
        }
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def update_user(
    user_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    age: Optional[int] = None,
) -> dict:
    """Update a user's information.

    Args:
        user_id: The user's ID
        name: New name (optional)
        email: New email (optional)
        age: New age (optional)

    Returns:
        The updated user object
    """
    try:
        # Build update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if email is not None:
            update_data["email"] = email
        if age is not None:
            update_data["age"] = age

        if not update_data:
            return {"error": "No fields to update"}

        db = db_manager.get_db()
        result = await db.merge(user_id, update_data)

        if not result:
            return {"error": f"User {user_id} not found"}

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return {
            "id": str(user_data.get("id", "")),
            "name": user_data["name"],
            "email": user_data["email"],
            "age": user_data.get("age"),
        }
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def delete_user(user_id: str) -> dict:
    """Delete a user from the database.

    Args:
        user_id: The user's ID

    Returns:
        Confirmation message
    """
    try:
        db = db_manager.get_db()
        result = await db.delete(user_id)

        if not result:
            return {"error": f"User {user_id} not found"}

        return {"message": f"User {user_id} deleted successfully"}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def execute_query(query: str) -> dict:
    """Execute a custom SurrealQL query.

    Args:
        query: The SurrealQL query to execute

    Returns:
        The query results
    """
    try:
        db = db_manager.get_db()
        result = await db.query(query)

        return {"result": result}
    except Exception as e:
        return {"error": f"Query error: {str(e)}"}
