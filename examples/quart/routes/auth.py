"""Authentication endpoints."""

from quart import Blueprint, jsonify, request

from database import get_db

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/signup", methods=["POST"])
async def signup():
    """Register a new user account."""
    try:
        data = await request.get_json()

        required_fields = ["namespace", "database", "access", "email", "password"]
        if not data or not all(field in data for field in required_fields):
            return jsonify(
                {"error": f"Missing required fields. Need: {', '.join(required_fields)}"}
            ), 400

        db = await get_db()
        token = await db.signup(
            {
                "namespace": data["namespace"],
                "database": data["database"],
                "access": data["access"],
                "email": data["email"],
                "password": data["password"],
            }
        )

        return jsonify(
            {
                "token": token,
                "message": "User registered successfully",
            }
        ), 201

    except Exception as e:
        return jsonify({"error": f"Signup failed: {str(e)}"}), 400


@bp.route("/signin", methods=["POST"])
async def signin():
    """Sign in to an account."""
    try:
        data = await request.get_json()

        if not data or "username" not in data or "password" not in data:
            return jsonify({"error": "Username and password are required"}), 400

        db = await get_db()
        token = await db.signin(
            {
                "username": data["username"],
                "password": data["password"],
            }
        )

        return jsonify(
            {
                "token": token,
                "message": "Signed in successfully",
            }
        ), 200

    except Exception as e:
        return jsonify({"error": f"Authentication failed: {str(e)}"}), 401


@bp.route("/invalidate", methods=["POST"])
async def invalidate():
    """Sign out and invalidate the session."""
    try:
        db = await get_db()
        await db.invalidate()

        return jsonify({"message": "Session invalidated successfully"}), 200

    except Exception as e:
        return jsonify({"error": f"Invalidation failed: {str(e)}"}), 500
