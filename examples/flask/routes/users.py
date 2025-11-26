"""User CRUD endpoints."""

import logging

from flask import Blueprint, jsonify, request

from database import get_db

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.route("", methods=["POST"])
def create_user():
    """Create a new user."""
    try:
        data = request.get_json()

        if not data or "name" not in data or "email" not in data:
            return jsonify({"error": "Name and email are required"}), 400

        db = get_db()
        result = db.create(
            "users",
            {
                "name": data["name"],
                "email": data["email"],
                "age": data.get("age"),
            },
        )

        if not result:
            return jsonify({"error": "Failed to create user"}), 500

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return jsonify(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            }
        ), 201

    except Exception as e:
        logging.error(f"Database error in create_user: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500


@bp.route("", methods=["GET"])
def list_users():
    """Get all users."""
    try:
        db = get_db()
        result = db.select("users")

        if not result:
            return jsonify([]), 200

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

        return jsonify(users), 200

    except Exception as e:
        logging.error(f"Database error in list_users: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500


@bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    """Get a user by ID."""
    try:
        db = get_db()
        result = db.select(user_id)

        if not result:
            return jsonify({"error": f"User {user_id} not found"}), 404

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return jsonify(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            }
        ), 200

    except Exception as e:
        logging.error(f"Database error in get_user: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500


@bp.route("/<user_id>", methods=["PUT"])
def update_user(user_id):
    """Update a user."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Build update data
        update_data = {}
        if "name" in data:
            update_data["name"] = data["name"]
        if "email" in data:
            update_data["email"] = data["email"]
        if "age" in data:
            update_data["age"] = data["age"]

        if not update_data:
            return jsonify({"error": "No fields to update"}), 400

        db = get_db()
        result = db.merge(user_id, update_data)

        if not result:
            return jsonify({"error": f"User {user_id} not found"}), 404

        # Handle both list and dict responses
        user_data = result[0] if isinstance(result, list) else result

        return jsonify(
            {
                "id": str(user_data.get("id", "")),
                "name": user_data["name"],
                "email": user_data["email"],
                "age": user_data.get("age"),
            }
        ), 200

    except Exception as e:
        logging.error(f"Database error in update_user: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500


@bp.route("/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Delete a user."""
    try:
        db = get_db()
        result = db.delete(user_id)

        if not result:
            return jsonify({"error": f"User {user_id} not found"}), 404

        return "", 204

    except Exception as e:
        logging.error(f"Database error in delete_user: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500
