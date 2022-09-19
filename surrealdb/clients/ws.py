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

from aiohttp import ClientSession
from aiohttp import ClientWebSocketResponse
from aiohttp import WSMsgType

from ..common import json as jsonlib
from ..common.exceptions import SurrealWebsocketException
from ..common.id import generate_id
from ..models import RPCError
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
    ) -> None:
        self._url = url

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

    async def disconnect(self) -> None:
        """Disconnects from the SurrealDB server."""
        self._recv_task.cancel()

        await self._ws.close()
        await self._client.close()

    def _receive_complete(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass

    async def _receive_task(self) -> None:
        async for msg in self._ws:
            if msg.type == WSMsgType.ERROR:
                raise SurrealWebsocketException(msg.data)

            json_response: Dict[str, Any] = jsonlib.loads(msg.data)

            error = json_response.get("error")
            if error is not None:
                error = RPCError(**error)
                raise SurrealWebsocketException(error.message)

            response = RPCResponse(**json_response)

            request_future = self._response_futures.pop(response.id, None)
            if request_future is not None:
                request_future.set_result(response)

    async def _send(
        self,
        method: str,
        *params: Any,
    ) -> Any:
        request = RPCRequest(
            id=generate_id(),
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
        namespace: str,
        database: str,
    ) -> None:
        """Changes the namespace and database to use."""
        response = await self._send("use", namespace, database)

        self._namespace = namespace
        self._database = database

        return response

    async def info(self) -> None:
        response = await self._send("info")
        return response

    async def signup(self, params: Dict[str, Any]) -> str:
        """Creates an account on the SurrealDB server.

        Parameters
        ----------
        params: :class:`Dict[str, Any]`
            The dict of params to pass to sign up.

        Returns
        -------
        :class:`str`
            A JWT token for the new account.
        """
        # if we send None, it's going to error so we must remove any none values
        sanitised_params = {k: v for k, v in params.items() if v is not None}

        response = await self._send("signup", sanitised_params)
        return response

    async def signin(self, params: Dict[str, Any]) -> None:
        """Signs in to the SurrealDB server.

        Parameters
        ----------
        params: :class:`Dict[str, Any]`
            The dict of params to pass to sign in.
        """
        # if we send None, it's going to error so we must remove any none values
        sanitised_params = {k: v for k, v in params.items() if v is not None}

        response = await self._send("signin", sanitised_params)
        return response

    async def invalidate(self) -> None:
        """Invalidates the current session."""
        response = await self._send("invalidate")
        return response

    async def authenticate(self, token: str) -> None:
        """Authenticates the current session.

        Parameters
        ----------
        token: :class:`str`
            The token to use for the connection.
        """
        response = await self._send("authenticate", token)
        return response

    async def live(self, table: str) -> None:
        response = await self._send("live", table)
        return response

    async def kill(self, id: str) -> None:
        response = await self._send("kill", id)
        return response

    async def let(self, key: str, value: Any) -> None:
        """Sets a value in the SurrealDB server.

        Parameters
        ----------
        key: :class:`str`
            The key to set.
        value: Any
            The value to set.
        """
        response = await self._send("let", key, value)
        return response

    async def set(self, key: str, value: Any) -> None:
        """Alias for :meth:`let`."""
        response = await self._send("set", key, value)
        return response

    async def query(self, sql: str, params: Any = None) -> List[List[Any]]:
        """Executes a SQL query.

        Parameters
        ----------
        sql: :class:`str`
            The SQL queries to execute.
        params: Any
            List of parameters which are part of the SQL queries.

        Returns
        -------
        List[List[Any]]
            The results for each query executed.
        """
        response = await self._send("query", sql, params)
        return [query_result["result"] for query_result in response]

    async def select_one(self, table_or_record_id: str) -> Optional[Dict[str, Any]]:
        """Selects a row from an SQL table.

        Parameters
        ----------
        table_or_record_id: :class:`str`
            The table or record ID to find.

        Returns
        -------
        Optional[Dict[:class:`str`, Any]]
            The first row found from the table or record ID, if any.
        """
        response = await self.select(table_or_record_id)
        if not response:
            return None

        return response[0]

    async def select(self, table_or_record_id: str) -> List[Dict[str, Any]]:
        """Selects rows from an SQL table.

        Parameters
        ----------
        table_or_record_id: :class:`str`
            The table or record ID to find.

        Returns
        -------
        List[Dict[:class:`str`, Any]]
            The results of the select.
        """
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

    async def update_one(self, record_id: str, data: Any) -> Dict[str, Any]:
        """Updates a record in the database.

        Parameters
        ----------
        record_id: :class:`str`
            The record ID to update the record.
        data: :class:`dict`
            The data to update the record with.

        Returns
        -------
        Dict[:class:`str`, Any]
            The updated record.
        """
        response = await self.update(record_id, data)
        return response[0]

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
            The data to update the record(s) with.

        Returns
        -------
        List[Dict[:class:`str`, Any]]`
            The updated records.
        """
        response = await self._send("update", table_or_record_id, data)
        return response

    async def change_one(self, record_id: str, data: Any) -> Dict[str, Any]:
        """Alias for :meth:`update_one`."""
        response = await self.change(record_id, data)
        return response[0]

    async def change(
        self,
        table_or_record_id: str,
        data: Any,
    ) -> List[Dict[str, Any]]:
        """Alias for :meth:`update`."""
        response = await self._send("change", table_or_record_id, data)
        return response

    async def modify_one(self, record_id: str, data: Any) -> Dict[str, Any]:
        """Modifies a record or table.

        Parameters
        ----------
        record_id: :class:`str`
            The record ID to modify.
        data: :class:`Any`
            The data to modify the record with.

        Returns
        -------
        Dict[:class:`str`, Any]
            A dictionary containing the diff of the record.
        """
        response = await self.modify(record_id, data)
        return response[0]

    async def modify(
        self,
        table_or_record_id: str,
        data: Any,
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
            A list of dictionaries containing the diff of the records.
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
