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
from __future__ import annotations

import asyncio
import dataclasses
from types import TracebackType
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Type
from weakref import WeakKeyDictionary

from aiohttp import ClientSession
from aiohttp import ClientWebSocketResponse
from aiohttp import WSMsgType

from ..common import json as jsonlib
from ..common.exceptions import SurrealWebsocketException
from ..common.id import generate_id
from ..models import RPCRequest
from ..models import RPCResponse

__all__ = ("WebsocketClient",)


class WebsocketClient:
    """Represents a websocket connection
    to a SurrealDB server.

    Parameters
    ----------
    url: :class:`str`
        The URL of the SurrealDB server.
    namespace: :class:`str`
        The namespace to use for the connection.
    database: :class:`str`
        The database to use for the connection.
    username: :class:`str`
        The username to use for the connection.
    password: :class:`str`
        The password to use for the connection.
    """

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

        self._client: ClientSession
        self._ws: ClientWebSocketResponse
        self._recv_task: asyncio.Task

        self._response_futures: Dict[str, asyncio.Future] = {}

    async def __aenter__(self) -> WebsocketClient:
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
        """Connects to the SurrealDB server."""
        self._client = ClientSession()
        self._ws = await self._client.ws_connect(self._url)

        self._recv_task = asyncio.create_task(self._receive_task())
        self._recv_task.add_done_callback(self._receive_complete)

        if self._token is not None:
            await self.authenticate(self._token)

        if self._username is not None and self._password is not None:
            await self.signin(username=self._username, password=self._password)

        if self._namespace is not None and self._database is not None:
            await self.use(self._namespace, self._database)

    async def disconnect(self) -> None:
        """Disconnects from the SurrealDB server."""
        self._recv_task.cancel()

        if isinstance(self._ws, ClientWebSocketResponse):
            await self._ws.close()

        if isinstance(self._client, ClientSession):
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

            json_response = jsonlib.loads(msg.data)
            response = RPCResponse(**json_response)
            if response.error is not None:
                raise SurrealWebsocketException(response.error.message)

            request_future = self._response_futures.pop(response.id, None)
            if request_future is not None:
                request_future.set_result(response)

    async def _send(
        self,
        method: str,
        *params: Any,
    ) -> Any:
        request = RPCRequest(
            id=generate_id(length=16),
            method=method,
            params=params,
        )
        await self._ws.send_json(dataclasses.asdict(request))

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._response_futures[request.id] = future

        response: RPCResponse = await asyncio.wait_for(future, timeout=None)
        return response.result

    async def ping(self) -> bool:
        """Pings the SurrealDB server."""
        response = await self._send("ping")
        return response

    async def use(
        self,
        namespace: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        """Changes the namespace and database to use."""
        response = await self._send("use", namespace, database)

        self._namespace = namespace
        self._database = database

        return response

    async def info(self) -> None:
        response = await self._send("info")
        return response

    async def signup(
        self,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        namespace: Optional[str] = None,
        database: Optional[str] = None,
        email: Optional[str] = None,
        scope: Optional[str] = None,
        interests: Optional[List[str]] = None,
    ) -> None:
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

    async def signin(
        self,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        namespace: Optional[str] = None,
        database: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        """Signs in to the SurrealDB server.

        Parameters
        ----------
        username: :class:`str`
            The username to use for the connection.
        password: :class:`str`
            The password to use for the connection.
        namespace: :class:`str`
            The namespace to use for the connection.
        database: :class:`str`
            The database to use for the connection.
        email: :class:`str`
            The email to use for the connection.
        """
        request_params = {
            "user": username,
            "pass": password,
            "email": email,
            "DB": database,
            "NS": namespace,
        }

        if username is not None:
            self._username = username

        if password is not None:
            self._password = password

        if namespace is not None:
            self._namespace = namespace

        if database is not None:
            self._database = database

        # if we send None, it's going to error so we must remove any none values
        sanitised_params = {k: v for k, v in request_params.items() if v is not None}

        response = await self._send("signin", sanitised_params)
        return response

    async def invalidate(self) -> None:
        """Invalidates the current session."""
        response = await self._send("invalidate")

        self._token = None

        return response

    async def authenticate(self, token: str) -> None:
        """Authenticates the current session.

        Parameters
        ----------
        token: :class:`str`
            The token to use for the connection.
        """
        response = await self._send("authenticate", token)

        self._token = token

        return response

    async def live(self, table: str) -> None:
        response = await self._send("live", table)
        return response

    async def kill(self, id: str) -> None:
        response = await self._send("kill", id)
        return response

    async def let(self, key: str, value: Any) -> None:
        response = await self._send("let", key, value)
        return response

    async def set(self, key: str, value: Any) -> None:
        """Sets a value in the SurrealDB server.

        Parameters
        ----------
        key: :class:`str`
            The key to set.
        value: Any
            The value to set.
        """
        response = await self._send("set", key, value)
        return response

    async def query(self, sql: str, params: Any) -> List[Dict[str, Any]]:
        """Executes a SQL query.

        Parameters
        ----------
        sql: :class:`str`
            The SQL query to execute.

        Returns
        -------
        List[Dict[:class:`str`, Any]]
        """
        response = await self._send("query", sql, params)
        return response

    async def select(self, table_or_record_id: str) -> List[Dict[str, Any]]:
        response = await self._send("select", table_or_record_id)
        return response

    async def create(
        self,
        table_or_record_id: str,
        data: Any,
    ) -> List[Dict[str, Any]]:
        """Creates a new record in the database.

        Parameters
        ----------
        table_or_record_id: :class:`str`
            The table or record ID to create the record in.
        data: :class:`dict`
            The data to create the record with.

        Returns
        -------
        List[Dict[:class:`str`, Any]]
            The created record.
        """
        response = await self._send("create", table_or_record_id, data)
        return response

    async def update(
        self,
        table_or_record_id: str,
        data: Any,
    ) -> List[Dict[str, Any]]:
        """Updates a record or records in a table.

        Parameters
        ----------
        table_or_record_id: :class:`str`
            The table or record ID to update.
        data: :class:`dict`
            The data to update the record with.

        Returns
        -------
        List[Dict[:class:`str`, Any]]`
            The updated records.
        """
        response = await self._send("update", table_or_record_id, data)
        return response

    async def change(
        self,
        table_or_record_id: str,
        **data: Any,
    ) -> List[Dict[str, Any]]:
        """Alias for :meth:`update`."""
        response = await self._send("change", table_or_record_id, data)
        return response

    async def modify(
        self,
        table_or_record_id: str,
        **data: Any,
    ) -> List[Dict[str, Any]]:
        """Modifies a record or table.

        Parameters
        ----------
        table_or_record_id: :class:`str`
            The table or record ID to modify.
        data: :class:`Any`
            The data to modify the record or table with.

        Returns
        -------
        List[Dict[:class:`str`, Any]]
            A list of dictionaries containing the deleted records.
        """
        response = await self._send("modify", table_or_record_id, data)
        return response

    async def delete(self, table_or_record_id: str) -> List[Dict[str, Any]]:
        """Deletes a record or table.

        Parameters
        ----------
        table_or_record_id: :class:`str`
            The table or record ID to delete.

        Returns
        -------
        List[Dict[:class:`str`, Any]]
            A list of dictionaries containing the deleted records.
        """
        response = await self._send("delete", table_or_record_id)
        return response
