"""Starlette + SurrealDB Example Application.

This example demonstrates:
- Minimal async CRUD operations with SurrealDB
- Authentication (signup, signin, invalidate)
- WebSocket live queries
- Lifespan management
- Middleware for CORS and errors
"""

from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from database import db_manager
from routes import auth, users, websocket


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager for Starlette."""
    # Startup
    await db_manager.connect()
    yield
    # Shutdown
    await db_manager.disconnect()


async def homepage(request):
    """Health check endpoint."""
    return JSONResponse(
        {
            "status": "healthy",
            "message": "SurrealDB Starlette Example API",
        }
    )


async def health(request):
    """Detailed health check."""
    return JSONResponse(
        {
            "status": "ok",
            "database": "connected",
        }
    )


# Define middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

# Create application
app = Starlette(
    debug=True,
    routes=[
        Route("/", homepage),
        Route("/health", health),
        *users.routes,
        *auth.routes,
        *websocket.routes,
    ],
    middleware=middleware,
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
