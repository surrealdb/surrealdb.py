"""Sanic + SurrealDB Example Application.

This example demonstrates:
- High-performance async CRUD operations with SurrealDB
- Authentication (signup, signin, invalidate)
- WebSocket live queries
- Blueprints for route organization
- Listeners for lifecycle management
"""

from sanic import Sanic, response
from sanic_cors import CORS

from blueprints import auth, users, websocket
from database import db_manager


def create_app():
    """Application factory."""
    app = Sanic("SurrealDB-Sanic-Example")

    # Initialize CORS
    CORS(app)

    # Register blueprints
    app.blueprint(users.bp)
    app.blueprint(auth.bp)
    app.blueprint(websocket.bp)

    # Listeners
    @app.before_server_start
    async def setup_db(app, loop):
        """Initialize database on startup."""
        await db_manager.connect()

    @app.after_server_stop
    async def cleanup_db(app, loop):
        """Cleanup database on shutdown."""
        await db_manager.disconnect()

    # Health check routes
    @app.get("/")
    async def index(request):
        return response.json(
            {
                "status": "healthy",
                "message": "SurrealDB Sanic Example API",
            }
        )

    @app.get("/health")
    async def health(request):
        return response.json(
            {
                "status": "ok",
                "database": "connected",
            }
        )

    # Error handlers
    @app.exception(Exception)
    async def handle_exception(request, exception):
        return response.json(
            {"error": str(exception)},
            status=500,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, auto_reload=True)
