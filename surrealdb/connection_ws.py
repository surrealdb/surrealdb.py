import logging
from typing import Tuple
from websockets import Subprotocol, ConnectionClosed

from surrealdb.connection import Connection
from surrealdb.errors import SurrealDbConnectionError
from websockets.asyncio.client import connect


class WebsocketConnection(Connection):
    def __init__(self, base_url: str, logger: logging.Logger):
        super().__init__(base_url, logger)

        self._ws = None

    async def connect(self):
        try:
            self._ws = await connect(self._base_url + "/rpc", subprotocols=[Subprotocol('cbor')])
        except Exception as e:
            raise SurrealDbConnectionError('cannot connect db server', e)

    async def use(self, namespace: str, database: str) -> None:
        self._namespace = namespace
        self._database = database

        await self.send("use", namespace, database)

    async def set(self, key: str, value):
        await self.send("let", key, value)

    async def unset(self, key: str):
        await self.send("unset", key)

    async def close(self):
        if self._ws:
            await self._ws.close()

    async def _make_request(self, request_payload: bytes) -> Tuple[bool, bytes]:
        try:
            await self._ws.send(request_payload)
            response = await self._ws.recv()
            return True, response
        except ConnectionClosed as e:
            raise SurrealDbConnectionError(e)
        except Exception as e:
            raise e
