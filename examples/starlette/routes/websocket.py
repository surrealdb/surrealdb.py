"""WebSocket endpoints for live queries."""

import asyncio

from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket
from surrealdb import AsyncSurreal

from config import settings


async def users_live_query(websocket: WebSocket):
    """WebSocket endpoint for real-time user updates."""
    await websocket.accept()

    # Create a new database connection for this WebSocket
    db = AsyncSurreal(settings.surrealdb_url)

    try:
        await db.connect()
        await db.signin(
            {
                "username": settings.surrealdb_username,
                "password": settings.surrealdb_password,
            }
        )
        await db.use(settings.surrealdb_namespace, settings.surrealdb_database)

        # Subscribe to live queries on the users table
        live_query_id = await db.live("users")

        await websocket.send_json(
            {
                "type": "connected",
                "message": "Subscribed to user updates",
                "live_query_id": str(live_query_id),
            }
        )

        # Process live query results
        async def process_live_results():
            """Process live query results and send to client."""
            try:
                async for result in db.subscribe_live(live_query_id):
                    await websocket.send_json(
                        {
                            "type": "update",
                            "data": result,
                        }
                    )
            except Exception as e:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Live query error: {str(e)}",
                    }
                )

        # Create task for processing live results
        live_task = asyncio.create_task(process_live_results())

        try:
            # Keep connection alive and handle incoming messages
            while True:
                data = await websocket.receive_text()
                # Echo back or handle client messages if needed
                await websocket.send_json(
                    {
                        "type": "echo",
                        "message": f"Received: {data}",
                    }
                )
        finally:
            # Clean up
            live_task.cancel()
            try:
                await live_task
            except asyncio.CancelledError:
                pass

            # Kill the live query
            try:
                await db.kill(live_query_id)
            except Exception:
                pass

    except Exception as e:
        await websocket.send_json(
            {
                "type": "error",
                "message": f"Connection error: {str(e)}",
            }
        )
    finally:
        await db.close()


# Define routes
routes = [
    WebSocketRoute("/ws/users", users_live_query),
]
