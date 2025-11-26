"""GraphQL + SurrealDB Example Application.

This example demonstrates:
- Modern GraphQL server with Strawberry
- Queries for data retrieval
- Mutations for data modification
- Subscriptions for real-time updates
- DataLoader for query optimization
- Type-safe schema with Python types
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from database import db_manager
from schema import schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI."""
    # Startup
    await db_manager.connect()
    yield
    # Shutdown
    await db_manager.disconnect()


# Create FastAPI application
app = FastAPI(
    title="SurrealDB GraphQL Example",
    description="GraphQL API powered by Strawberry and SurrealDB",
    version="1.0.0",
    lifespan=lifespan,
)

# Create GraphQL router with GraphiQL interface
graphql_app = GraphQLRouter(
    schema,
    graphiql=True,  # Enable GraphiQL playground
)

# Mount GraphQL endpoint
app.include_router(graphql_app, prefix="/graphql")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "SurrealDB GraphQL API",
        "graphql": "/graphql",
        "playground": "/graphql (in browser)",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
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
