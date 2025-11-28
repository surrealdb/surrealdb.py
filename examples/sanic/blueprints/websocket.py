"""WebSocket endpoints for live queries."""

import asyncio
import json

from sanic import Blueprint
from surrealdb import AsyncSurreal

from config import config

bp = Blueprint("websocket")


@bp.websocket("/ws/users")
async def users_live_query(request, ws):
    """WebSocket endpoint for real-time user updates."""
    # Create a new database connection for this WebSocket
    db = AsyncSurreal(config.SURREALDB_URL)

    try:
        await db.connect()
        await db.signin(
            {
                "username": config.SURREALDB_USERNAME,
                "password": config.SURREALDB_PASSWORD,
            }
        )
        await db.use(config.SURREALDB_NAMESPACE, config.SURREALDB_DATABASE)

        # Subscribe to live queries on the users table
        live_query_id = await db.live("users")

        await ws.send(
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
                    await ws.send(
                        json.dumps(
                            {
                                "type": "update",
                                "data": result,
                            }
                        )
                    )
            except Exception as e:
                await ws.send(
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
            async for data in ws:
                # Echo back or handle client messages if needed
                await ws.send(
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
        await ws.send(
            json.dumps(
                {
                    "type": "error",
                    "message": f"Connection error: {str(e)}",
                }
            )
        )
    finally:
        await db.close()
