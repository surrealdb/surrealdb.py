"""FastAPI + SurrealDB Example Application.

This example demonstrates:
- CRUD operations with SurrealDB
- Authentication (signup, signin, invalidate)
- Live queries via WebSocket
- Dependency injection
- Type safety with Pydantic
- Auto-generated API documentation
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import lifespan
from routes import auth, users, websocket

# Create FastAPI application
app = FastAPI(
    title="SurrealDB FastAPI Example",
    description="A comprehensive example of SurrealDB integration with FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(websocket.router)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "SurrealDB FastAPI Example API",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Detailed health check."""
    return {
        "status": "ok",
        "database": "connected",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
