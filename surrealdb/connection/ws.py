import websockets

from typing import Optional
from surrealdb.connection.connection import Connection


class WebsocketConnection(Connection):
    def __init__(self, base_url: str, namespace: Optional[str] = None, database: Optional[str] = None):
        super().__init__(base_url, namespace, database)

        self._ws = None

    async def connect(self):
        try:
            self._ws = await websockets.connect(self._base_url + "/rpc", subprotocols=['cbor'])
        except Exception as e:
            raise Exception('cannot connect websocket server', e)

    async def use(self, namespace: str, database: str) -> None:
        self._namespace = namespace
        self._database = database

        await self.send("use", namespace, database)

    async def close(self):
        if self._ws:
            await self._ws.close()

    async def _make_request(self, request_payload: bytes) -> bytes:
        try:
            await self._ws.send(request_payload)
            response = await self._ws.recv()
            return response
        except websockets.ConnectionClosed:
            print("conn closed")
        except Exception as e:
            print("failed", e)
