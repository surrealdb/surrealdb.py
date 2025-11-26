"""Litestar + SurrealDB Example Application.

This example demonstrates:
- Modern async CRUD operations with SurrealDB
- Authentication (signup, signin, invalidate)
- DTOs for type safety
- Dependency injection
- WebSocket live queries
- Lifecycle hooks
"""

from litestar import Litestar, get
from litestar.config.cors import CORSConfig

from controllers.auth import AuthController
from controllers.users import UserController
from controllers.websocket import WebSocketController
from database import db_manager


@get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "SurrealDB Litestar Example API",
        "docs": "/schema",
    }


@get("/health")
async def health_check() -> dict[str, str]:
    """Detailed health check."""
    return {
        "status": "ok",
        "database": "connected",
    }


async def startup() -> None:
    """Startup hook."""
    await db_manager.connect()


async def shutdown() -> None:
    """Shutdown hook."""
    await db_manager.disconnect()


# Configure CORS
cors_config = CORSConfig(
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create application
app = Litestar(
    route_handlers=[
        root,
        health_check,
        UserController,
        AuthController,
        WebSocketController,
    ],
    cors_config=cors_config,
    on_startup=[startup],
    on_shutdown=[shutdown],
    debug=True,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
