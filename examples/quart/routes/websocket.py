"""WebSocket endpoints for live queries."""

import asyncio
import json

from quart import Blueprint, websocket
from surrealdb import AsyncSurreal

from config import config

bp = Blueprint("websocket", __name__)


@bp.websocket("/ws/users")
async def users_live_query():
    """WebSocket endpoint for real-time user updates."""
    # Create a new database connection for this WebSocket
    cfg = config["default"]
    db = AsyncSurreal(cfg.SURREALDB_URL)

    try:
        await db.connect()
        await db.signin(
            {
                "username": cfg.SURREALDB_USERNAME,
                "password": cfg.SURREALDB_PASSWORD,
            }
        )
        await db.use(cfg.SURREALDB_NAMESPACE, cfg.SURREALDB_DATABASE)

        # Subscribe to live queries on the users table
        live_query_id = await db.live("users")

        await websocket.send(
            json.dumps(
                {
                    "type": "connected",
                    "message": "Subscribed to user updates",
                    "live_query_id": str(live_query_id),
                }
            )
        )

        # Process live query results
        async def process_live_results():
            """Process live query results and send to client."""
            try:
                async for result in db.subscribe_live(live_query_id):
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "update",
                                "data": result,
                            }
                        )
                    )
            except Exception as e:
                await websocket.send(
                    json.dumps(
                        {
                            "type": "error",
                            "message": f"Live query error: {str(e)}",
                        }
                    )
                )

        # Create task for processing live results
        live_task = asyncio.create_task(process_live_results())

        try:
            # Keep connection alive and handle incoming messages
            while True:
                data = await websocket.receive()
                # Echo back or handle client messages if needed
                await websocket.send(
                    json.dumps(
                        {
                            "type": "echo",
                            "message": f"Received: {data}",
                        }
                    )
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
        await websocket.send(
            json.dumps(
                {
                    "type": "error",
                    "message": f"Connection error: {str(e)}",
                }
            )
        )
    finally:
        await db.close()
