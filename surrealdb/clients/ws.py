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
import asyncio
from types import TracebackType
from typing import Any
from typing import Awaitable
from typing import Optional
from typing import Type

from aiohttp import ClientSession
from aiohttp import ClientWebSocketResponse
from aiohttp import WSMsgType

from ..common import json as jsonlib
from ..common.exceptions import SurrealWebsocketException
from ..common.id import generate_id
from ..models import RPCRequest
from ..models import RPCResponse

__all__ = ("SurrealDBWSClient",)


class SurrealDBWSClient:
    def __init__(
        self,
        url: str,
        *,
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        namespace: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self._url = url
        self._token = token
        self._username = username
        self._password = password
        self._namespace = namespace
        self._database = database

        self._client = ClientSession
        self._ws: ClientWebSocketResponse
        self._recv_task: asyncio.Task

        self._responses: dict[str, RPCResponse] = {}

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

        self._recv_task = asyncio.create_task(self._receive_task())
        self._recv_task.add_done_callback(self._receive_complete)

        if self._token is not None:
            await self.authenticate(self._token)

        if self._username is not None and self._password is not None:
            await self.sign_in(username=self._username, password=self._password)

        if self._namespace is not None and self._database is not None:
            await self.use(self._namespace, self._database)

    async def disconnect(self) -> None:
        self._recv_task.cancel()

        await self._ws.close()
        await self._client.close()

    def _receive_complete(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            raise e

    async def _receive_task(self) -> None:
        async for msg in self._ws:
            if msg.type == WSMsgType.ERROR:
                raise SurrealWebsocketException(msg.data)

            response: RPCResponse = jsonlib.loads(msg.data)
            if response.get("error") is not None:
                raise SurrealWebsocketException(response["error"]["message"])

            self._responses[response["id"]] = response

    async def _wait_response(self, id: str) -> RPCResponse:
        while id not in self._responses:
            await asyncio.sleep(0.1)

        response = self._responses.pop(id)
        return response

    async def _send(
        self,
        method: str,
        *params: Any,
    ) -> Any:
        request: RPCRequest = {
            "id": generate_id(length=16),
            "method": method,
            "params": params,
        }

        await self._ws.send_json(request)

        response = await self._wait_response(request["id"])
        return response["result"]

    async def ping(self) -> Any:
        response = await self._send("ping")
        return response

    async def use(self, namespace: str, database: str) -> Any:
        response = await self._send("use", namespace, database)

        self._namespace = namespace
        self._database = database

        return response

    async def info(self) -> Any:
        response = await self._send("info")
        return response

    async def sign_up(
        self,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        namespace: Optional[str] = None,
        database: Optional[str] = None,
        email: Optional[str] = None,
        scope: Optional[str] = None,
        interests: Optional[list[str]] = None,
    ) -> Any:
        request_params = {
            "user": username,
            "pass": password,
            "email": email,
            "DB": database,
            "NS": namespace,
            "SC": scope,
            "interests": interests,
        }

        # if we send None, it's going to error so we must remove any none values
        sanitised_params = {k: v for k, v in request_params.items() if v is not None}

        response = await self._send("signup", sanitised_params)
        return response

    async def sign_in(
        self,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        namespace: Optional[str] = None,
        database: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Any:
        request_params = {
            "user": username,
            "pass": password,
            "email": email,
            "DB": database,
            "NS": namespace,
        }

        # if we send None, it's going to error so we must remove any none values
        sanitised_params = {k: v for k, v in request_params.items() if v is not None}

        response = await self._send("signin", sanitised_params)
        return response

    async def invalidate(self) -> Any:
        response = await self._send("invalidate")

        self._token = None

        return response

    async def authenticate(self, token: str) -> Any:
        response = await self._send("authenticate", token)

        self._token = token

        return response

    async def live(self, table: str) -> Any:
        response = await self._send("live", table)
        return response

    async def kill(self, query: str) -> Any:
        response = await self._send("kill", query)
        return response

    async def let(self, key: str, value: Any) -> Any:
        response = await self._send("let", key, value)
        return response

    async def query(self, sql: str, **kwargs: Any) -> Any:
        response = await self._send("query", sql, kwargs)
        return response

    async def select(self, what: str) -> Any:
        response = await self._send("select", what)
        return response

    async def create(self, thing: str, **data: Any) -> Any:
        response = await self._send("create", thing, data)
        return response

    async def update(self, thing: str, **data: Any) -> Any:
        response = await self._send("update", thing, data)
        return response

    async def change(self, thing: str, **data: Any) -> Any:
        response = await self._send("change", thing, data)
        return response

    async def modify(self, thing: str, **data: Any) -> Any:
        response = await self._send("modify", thing, data)
        return response

    async def delete(self, what: str) -> Any:
        response = await self._send("delete", what)
        return response
