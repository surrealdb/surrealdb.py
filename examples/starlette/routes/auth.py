"""Authentication endpoints."""

from starlette.responses import JSONResponse
from starlette.routing import Route

from database import db_manager


async def signup(request):
    """Register a new user account."""
    try:
        data = await request.json()

        required_fields = ["namespace", "database", "access", "email", "password"]
        if not data or not all(field in data for field in required_fields):
            return JSONResponse(
                {"error": f"Missing required fields. Need: {', '.join(required_fields)}"},
                status_code=400,
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

        return JSONResponse(
            {
                "token": token,
                "message": "User registered successfully",
            },
            status_code=201,
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Signup failed: {str(e)}"},
            status_code=400,
        )


async def signin(request):
    """Sign in to an account."""
    try:
        data = await request.json()

        if not data or "username" not in data or "password" not in data:
            return JSONResponse(
                {"error": "Username and password are required"},
                status_code=400,
            )

        db = db_manager.get_db()
        token = await db.signin(
            {
                "username": data["username"],
                "password": data["password"],
            }
        )

        return JSONResponse(
            {
                "token": token,
                "message": "Signed in successfully",
            },
            status_code=200,
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Authentication failed: {str(e)}"},
            status_code=401,
        )


async def invalidate(request):
    """Sign out and invalidate the session."""
    try:
        db = db_manager.get_db()
        await db.invalidate()

        return JSONResponse(
            {"message": "Session invalidated successfully"},
            status_code=200,
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Invalidation failed: {str(e)}"},
            status_code=500,
        )


# Define routes
routes = [
    Route("/auth/signup", signup, methods=["POST"]),
    Route("/auth/signin", signin, methods=["POST"]),
    Route("/auth/invalidate", invalidate, methods=["POST"]),
]
