"""User CRUD endpoints."""

from starlette.responses import JSONResponse
from starlette.routing import Route

from database import db_manager


async def create_user(request):
    """Create a new user."""
    try:
        data = await request.json()

        if not data or "name" not in data or "email" not in data:
            return JSONResponse(
                {"error": "Name and email are required"},
                status_code=400,
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
            return JSONResponse(
                {"error": "Failed to create user"},
                status_code=500,
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return JSONResponse(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            },
            status_code=201,
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Database error: {str(e)}"},
            status_code=500,
        )


async def list_users(request):
    """Get all users."""
    try:
        db = db_manager.get_db()
        result = await db.select("users")

        if not result:
            return JSONResponse([], status_code=200)

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

        return JSONResponse(users, status_code=200)

    except Exception as e:
        return JSONResponse(
            {"error": f"Database error: {str(e)}"},
            status_code=500,
        )


async def get_user(request):
    """Get a user by ID."""
    try:
        user_id = request.path_params["user_id"]

        db = db_manager.get_db()
        result = await db.select(user_id)

        if not result:
            return JSONResponse(
                {"error": f"User {user_id} not found"},
                status_code=404,
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return JSONResponse(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            },
            status_code=200,
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Database error: {str(e)}"},
            status_code=500,
        )


async def update_user(request):
    """Update a user."""
    try:
        user_id = request.path_params["user_id"]
        data = await request.json()

        if not data:
            return JSONResponse(
                {"error": "No data provided"},
                status_code=400,
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
            return JSONResponse(
                {"error": "No fields to update"},
                status_code=400,
            )

        db = db_manager.get_db()
        result = await db.merge(user_id, update_data)

        if not result:
            return JSONResponse(
                {"error": f"User {user_id} not found"},
                status_code=404,
            )

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return JSONResponse(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            },
            status_code=200,
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Database error: {str(e)}"},
            status_code=500,
        )


async def delete_user(request):
    """Delete a user."""
    try:
        user_id = request.path_params["user_id"]

        db = db_manager.get_db()
        result = await db.delete(user_id)

        if not result:
            return JSONResponse(
                {"error": f"User {user_id} not found"},
                status_code=404,
            )

        return JSONResponse(None, status_code=204)

    except Exception as e:
        return JSONResponse(
            {"error": f"Database error: {str(e)}"},
            status_code=500,
        )


# Define routes
routes = [
    Route("/users", create_user, methods=["POST"]),
    Route("/users", list_users, methods=["GET"]),
    Route("/users/{user_id}", get_user, methods=["GET"]),
    Route("/users/{user_id}", update_user, methods=["PUT"]),
    Route("/users/{user_id}", delete_user, methods=["DELETE"]),
]
