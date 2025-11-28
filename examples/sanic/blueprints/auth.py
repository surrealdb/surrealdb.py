"""Authentication endpoints."""

from sanic import Blueprint, response

from database import db_manager

bp = Blueprint("auth", url_prefix="/api/auth")


@bp.post("/signup")
async def signup(request):
    """Register a new user account."""
    try:
        data = request.json

        required_fields = ["namespace", "database", "access", "email", "password"]
        if not data or not all(field in data for field in required_fields):
            return response.json(
                {"error": f"Missing required fields. Need: {', '.join(required_fields)}"},
                status=400,
            )

        db = db_manager.get_db()
        token = await db.signup(
            {
                "namespace": data["namespace"],
                "database": data["database"],
                "access": data["access"],
                "email": data["email"],
                "password": data["password"],
            }
        )

        return response.json(
            {
                "token": token,
                "message": "User registered successfully",
            },
            status=201,
        )

    except Exception as e:
        return response.json(
            {"error": f"Signup failed: {str(e)}"},
            status=400,
        )


@bp.post("/signin")
async def signin(request):
    """Sign in to an account."""
    try:
        data = request.json

        if not data or "username" not in data or "password" not in data:
            return response.json(
                {"error": "Username and password are required"},
                status=400,
            )

        db = db_manager.get_db()
        token = await db.signin(
            {
                "username": data["username"],
                "password": data["password"],
            }
        )

        return response.json(
            {
                "token": token,
                "message": "Signed in successfully",
            },
            status=200,
        )

    except Exception as e:
        return response.json(
            {"error": f"Authentication failed: {str(e)}"},
            status=401,
        )


@bp.post("/invalidate")
async def invalidate(request):
    """Sign out and invalidate the session."""
    try:
        db = db_manager.get_db()
        await db.invalidate()

        return response.json(
            {"message": "Session invalidated successfully"},
            status=200,
        )

    except Exception as e:
        return response.json(
            {"error": f"Invalidation failed: {str(e)}"},
            status=500,
        )
