"""User CRUD endpoints."""

from sanic import Blueprint, response

from database import db_manager

bp = Blueprint("users", url_prefix="/api/users")


@bp.post("")
async def create_user(request):
    """Create a new user."""
    try:
        data = request.json

        if not data or "name" not in data or "email" not in data:
            return response.json(
                {"error": "Name and email are required"},
                status=400,
            )

        db = db_manager.get_db()
        result = await db.create(
            "users",
            {
                "name": data["name"],
                "email": data["email"],
                "age": data.get("age"),
            },
        )

        if not result:
            return response.json(
                {"error": "Failed to create user"},
                status=500,
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return response.json(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            },
            status=201,
        )

    except Exception as e:
        return response.json(
            {"error": f"Database error: {str(e)}"},
            status=500,
        )


@bp.get("")
async def list_users(request):
    """Get all users."""
    try:
        db = db_manager.get_db()
        result = await db.select("users")

        if not result:
            return response.json([], status=200)

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

        return response.json(users, status=200)

    except Exception as e:
        return response.json(
            {"error": f"Database error: {str(e)}"},
            status=500,
        )


@bp.get("/<user_id>")
async def get_user(request, user_id):
    """Get a user by ID."""
    try:
        db = db_manager.get_db()
        result = await db.select(user_id)

        if not result:
            return response.json(
                {"error": f"User {user_id} not found"},
                status=404,
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return response.json(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            },
            status=200,
        )

    except Exception as e:
        return response.json(
            {"error": f"Database error: {str(e)}"},
            status=500,
        )


@bp.put("/<user_id>")
async def update_user(request, user_id):
    """Update a user."""
    try:
        data = request.json

        if not data:
            return response.json(
                {"error": "No data provided"},
                status=400,
            )

        # Build update data
        update_data = {}
        if "name" in data:
            update_data["name"] = data["name"]
        if "email" in data:
            update_data["email"] = data["email"]
        if "age" in data:
            update_data["age"] = data["age"]

        if not update_data:
            return response.json(
                {"error": "No fields to update"},
                status=400,
            )

        db = db_manager.get_db()
        result = await db.merge(user_id, update_data)

        if not result:
            return response.json(
                {"error": f"User {user_id} not found"},
                status=404,
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return response.json(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            },
            status=200,
        )

    except Exception as e:
        return response.json(
            {"error": f"Database error: {str(e)}"},
            status=500,
        )


@bp.delete("/<user_id>")
async def delete_user(request, user_id):
    """Delete a user."""
    try:
        db = db_manager.get_db()
        result = await db.delete(user_id)

        if not result:
            return response.json(
                {"error": f"User {user_id} not found"},
                status=404,
            )

        return response.empty(status=204)

    except Exception as e:
        return response.json(
            {"error": f"Database error: {str(e)}"},
            status=500,
        )
