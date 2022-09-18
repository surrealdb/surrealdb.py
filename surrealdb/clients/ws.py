"""
Copyright © SurrealDB Ltd

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from types import TracebackType
from typing import Any
from typing import Optional
from typing import Type

from aiohttp import ClientSession
from aiohttp import ClientWebSocketResponse

from ..common.id import generate_id

__all__ = ("SurrealDBWSClient",)


class SurrealDBWSClient:
    def __init__(self, url: str, token: Optional[str] = None) -> None:
        self._url = url
        self._token = token
        self._client = ClientSession
        self._ws: ClientWebSocketResponse

    async def __aenter__(self) -> "SurrealDBWSClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        self._client = ClientSession()
        self._ws = await self._client.ws_connect(self._url)

        if self._token is not None:
            await self.authenticate(self._token)

    async def disconnect(self) -> None:
        await self._ws.close()
        await self._client.close()

    async def _send(self, method: str, *params: Any) -> None:
        request = {
            "id": generate_id(length=16),
            "method": method,
            "params": params,
        }

        await self._ws.send_json(request)

    async def authenticate(self, token: str) -> None:
        await self._send("authenticate", token)
        self._token = token
