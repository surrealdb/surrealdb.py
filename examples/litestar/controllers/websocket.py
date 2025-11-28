"""WebSocket endpoints for live queries."""

import asyncio

from litestar import WebSocket, websocket, websocket_listener
from litestar.controller import Controller
from litestar.exceptions import WebSocketDisconnect
from surrealdb import AsyncSurreal

from config import settings


@websocket_listener("/ws/users")
async def users_live_query(data: str) -> str:
    """WebSocket endpoint for real-time user updates."""
    # Note: This is a simplified example. In production, you'd want
    # to manage the database connection and live query lifecycle properly.
    # Litestar's websocket_listener has a different pattern than other frameworks.
    return f"Echo: {data}"


# Alternative approach using the WebSocket class directly


class WebSocketController(Controller):
    """WebSocket controller."""

    @websocket("/ws/users")
    async def users_live_query_handler(self, socket: WebSocket) -> None:
        """WebSocket endpoint for real-time user updates."""
        await socket.accept()

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

            await socket.send_json(
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
                        await socket.send_json(
                            {
                                "type": "update",
                                "data": result,
                            }
                        )
                except Exception as e:
                    await socket.send_json(
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
                    data = await socket.receive_text()
                    # Echo back or handle client messages if needed
                    await socket.send_json(
                        {
                            "type": "echo",
                            "message": f"Received: {data}",
                        }
                    )
            except WebSocketDisconnect:
                pass
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
            await socket.send_json(
                {
                    "type": "error",
                    "message": f"Connection error: {str(e)}",
                }
            )
        finally:
            await db.close()
