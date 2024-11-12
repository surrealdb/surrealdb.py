import websockets

from typing import Optional, Tuple
from surrealdb.connection import Connection
from surrealdb.errors import SurrealDbConnectionError


class WebsocketConnection(Connection):
    def __init__(self, base_url: str, namespace: Optional[str] = None, database: Optional[str] = None):
        super().__init__(base_url, namespace, database)

        self._ws = None

    async def connect(self):
        try:
            self._ws = await websockets.connect(self._base_url + "/rpc", subprotocols=['cbor'])
        except Exception as e:
            raise SurrealDbConnectionError('cannot connect db server', e)

    async def use(self, namespace: str, database: str) -> None:
        self._namespace = namespace
        self._database = database

        await self.send("use", namespace, database)

    async def close(self):
        if self._ws:
            await self._ws.close()

    async def _make_request(self, request_payload: bytes) -> Tuple[bool, bytes]:
        try:
            await self._ws.send(request_payload)
            response = await self._ws.recv()
            return True, response
        except websockets.ConnectionClosed as e:
            raise SurrealDbConnectionError(e)
        except Exception as e:
            raise e
