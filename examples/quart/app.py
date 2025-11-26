"""Quart + SurrealDB Example Application.

This example demonstrates:
- Async CRUD operations with SurrealDB
- Authentication (signup, signin, invalidate)
- WebSocket live queries
- Blueprints for route organization
- Request-scoped database connections
"""

import os

from quart import Quart, jsonify
from quart_cors import cors

from config import config
from database import init_app
from routes import auth, users, websocket


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.getenv("QUART_ENV", "development")

    app = Quart(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    app = cors(app, allow_origin="*")
    init_app(app)

    # Register blueprints
    app.register_blueprint(users.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(websocket.bp)

    # Health check routes
    @app.route("/")
    async def index():
        return jsonify(
            {
                "status": "healthy",
                "message": "SurrealDB Quart Example API",
            }
        )

    @app.route("/health")
    async def health():
        return jsonify(
            {
                "status": "ok",
                "database": "connected",
            }
        )

    # Error handlers
    @app.errorhandler(404)
    async def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    async def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
