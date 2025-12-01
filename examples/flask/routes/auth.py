"""Authentication endpoints."""

import logging
import traceback

from flask import Blueprint, jsonify, request

from database import get_db

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

logger = logging.getLogger(__name__)


@bp.route("/signup", methods=["POST"])
def signup():
    """Register a new user account."""
    try:
        data = request.get_json()

        required_fields = ["namespace", "database", "access", "email", "password"]
        if not data or not all(field in data for field in required_fields):
            return jsonify(
                {"error": f"Missing required fields. Need: {', '.join(required_fields)}"}
            ), 400

        db = get_db()
        token = db.signup(
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
        logger.error("Exception in signup: %s\n%s", str(e), traceback.format_exc())
        return jsonify({"error": "Signup failed. Please try again later."}), 400


@bp.route("/signin", methods=["POST"])
def signin():
    """Sign in to an account."""
    try:
        data = request.get_json()

        if not data or "username" not in data or "password" not in data:
            return jsonify({"error": "Username and password are required"}), 400

        db = get_db()
        token = db.signin(
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
        logger.error("Exception in signin: %s\n%s", str(e), traceback.format_exc())
        return jsonify({"error": "Authentication failed. Please try again."}), 401


@bp.route("/invalidate", methods=["POST"])
def invalidate():
    """Sign out and invalidate the session."""
    try:
        db = get_db()
        db.invalidate()

        return jsonify({"message": "Session invalidated successfully"}), 200

    except Exception as e:
        logger.error("Exception in invalidate: %s\n%s", str(e), traceback.format_exc())
        return jsonify({"error": "Invalidation failed. Please try again later."}), 500
