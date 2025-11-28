"""Flask + SurrealDB Example Application.

This example demonstrates:
- CRUD operations with SurrealDB
- Authentication (signup, signin, invalidate)
- Application factory pattern
- Blueprints for route organization
- Request-scoped database connections
"""

import os

from flask import Flask, jsonify
from flask_cors import CORS

from config import config
from database import init_app
from routes import auth, users


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    CORS(app)
    init_app(app)

    # Register blueprints
    app.register_blueprint(users.bp)
    app.register_blueprint(auth.bp)

    # Health check routes
    @app.route("/")
    def index():
        return jsonify(
            {
                "status": "healthy",
                "message": "SurrealDB Flask Example API",
            }
        )

    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "database": "connected",
            }
        )

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
