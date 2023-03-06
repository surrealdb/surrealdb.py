"""
Copyright © SurrealDB Ltd.

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
from typing import Any, Dict, List, Optional, Type

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

from ..common import json as jsonlib
from ..common.exceptions import SurrealWebsocketException
from ..common.id import generate_id
from ..models import RPCError, RPCRequest, RPCResponse

__all__ = ("WebsocketClient",)


class WebsocketClient:
    """Represents a websocket connection to a SurrealDB server.

    Args:
        url: The URL of the SurrealDB server.
    """

    def __init__(self, url: str) -> None:
        self._url = url

        self._client: ClientSession
        self._ws: ClientWebSocketResponse
        self._recv_task: asyncio.Task

        self._response_futures: Dict[str, asyncio.Future] = {}

    async def __aenter__(self) -> WebsocketClient:
        """Create a websocket connection when entering the context manager."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        """Disconnect the websocket client when exiting the context manager."""
        await self.disconnect()

    async def connect(self) -> None:
        """Connect to the SurrealDB server."""
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
            json_response: Dict[str, Any] = jsonlib.loads(msg.data)
            request_future = self._response_futures.pop(json_response["id"], None)

            if request_future is None:
                # SurrealDB returned an answer to a non existent operation
                raise SurrealWebsocketException(
                    "Invalid operation id received from server"
                )

            if msg.type == WSMsgType.ERROR:
                request_future.set_exception(SurrealWebsocketException(msg.data))
                continue

            error = json_response.get("error")

            if error is not None:
                error = RPCError(**error)
                request_future.set_exception(SurrealWebsocketException(error.message))
                continue

            response = RPCResponse(**json_response)

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

    async def use(self, namespace: str, database: str) -> None:
        """Change the namespace and database to use.

        Args:
            namespace: The namespace to use.
            database: The database to use.
        """
        response = await self._send("use", namespace, database)

        self._namespace = namespace
        self._database = database

        return response

    async def info(self) -> None:
        """Get current authentication information."""
        response = await self._send("info")
        return response

    async def signup(self, params: Dict[str, Any]) -> str:
        """Create an account on the SurrealDB server.

        Args:
            params: The dict of params to pass to sign up.

        Returns:
            A JWT token for the new account.
        """
        # if we send None, it's going to error so we must remove any none values
        sanitised_params = {k: v for k, v in params.items() if v is not None}

        response = await self._send("signup", sanitised_params)
        return response

    async def signin(self, params: Dict[str, Any]) -> None:
        """Signs in to the SurrealDB server.

        Args:
            params: The dict of params to pass to sign in.
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
        """Authenticate the current session.

        Args:
            token: The token to use for the connection.
        """
        response = await self._send("authenticate", token)
        return response

    async def live(self, table: str) -> None:  # noqa: D102
        response = await self._send("live", table)
        return response

    async def kill(self, id: str) -> None:  # noqa: D102
        response = await self._send("kill", id)
        return response

    async def let(self, key: str, value: Any) -> None:
        """Set a value in the SurrealDB server.

        Args:
            key: The key to set.
            value: The value to set.
        """
        response = await self._send("let", key, value)
        return response

    async def set(self, key: str, value: Any) -> None:
        """Alias for `let`.

        Args:
            key: The key to set.
            value: The value to set.
        """
        response = await self._send("set", key, value)
        return response

    async def query(self, sql: str, params: Any = None) -> List[List[Any]]:
        """Execute a SQL query.

        Args:
            sql: The SQL queries to execute.
            params: List of parameters which are part of the SQL queries.

        Returns:
            The results for each query executed.
        """
        response = await self._send("query", sql, params)
        return [query_result["result"] for query_result in response]

    async def select_one(self, table_or_record_id: str) -> Optional[Dict[str, Any]]:
        """Select a row from an SQL table.

        Args:
            table_or_record_id: The table or record ID to find.

        Returns:
            The first row found from the table or record ID, if any.
        """
        response = await self.select(table_or_record_id)
        if not response:
            return None

        return response[0]

    async def select(self, table_or_record_id: str) -> List[Dict[str, Any]]:
        """Select rows from an SQL table.

        Args:
            table_or_record_id: The table or record ID to find.

        Returns:
            The results of the select.
        """
        response = await self._send("select", table_or_record_id)
        return response

    async def create(self, table_or_record_id: str, data: Any) -> List[Dict[str, Any]]:
        """Create a new record in the database.

        Args:
            table_or_record_id: The table or record ID to create the record in.
            data: The data to create the record with.

        Returns:
            The created record.
        """
        response = await self._send("create", table_or_record_id, data)
        return response

    async def update_one(self, record_id: str, data: Any) -> Dict[str, Any]:
        """Update a record in the database.

        Args:
            record_id: The record ID to update the record.
            data: The data to update the record with.

        Returns:
            The updated record.
        """
        response = await self.update(record_id, data)
        return response[0]

    async def update(
        self,
        table_or_record_id: str,
        data: Any,
    ) -> List[Dict[str, Any]]:
        """Update a record or records in a table.

        Args:
            table_or_record_id: The table or record ID to update.
            data: The data to update the record(s) with.

        Returns:
            The updated records.
        """
        response = await self._send("update", table_or_record_id, data)
        return response

    async def change_one(self, record_id: str, data: Any) -> Dict[str, Any]:
        """Alias for `update_one`.

        Args:
            record_id: The record ID to change.
            data: The data to change the record with.

        Returns:
            A dictionary containing the diff of the record.
        """
        response = await self.change(record_id, data)
        return response[0]

    async def change(self, table_or_record_id: str, data: Any) -> List[Dict[str, Any]]:
        """Alias for `update`.

        Args:
            table_or_record_id: The table or record ID to change.
            data: The data to change the record or table with.

        Returns:
            A list of dictionaries containing the diff of the records.
        """
        response = await self._send("change", table_or_record_id, data)
        return response

    async def modify_one(self, record_id: str, data: Any) -> Dict[str, Any]:
        """Modify a record or table.

        Args:
            record_id: The record ID to modify.
            data: The data to modify the record with.

        Returns:
            A dictionary containing the diff of the record.
        """
        response = await self.modify(record_id, data)
        return response[0]

    async def modify(self, table_or_record_id: str, data: Any) -> List[Dict[str, Any]]:
        """Modify a record or table.

        Args:
            table_or_record_id: The table or record ID to modify.
            data: The data to modify the record or table with.

        Returns:
            A list of dictionaries containing the diff of the records.
        """
        response = await self._send("modify", table_or_record_id, data)
        return response

    async def delete(self, table_or_record_id: str) -> List[Dict[str, Any]]:
        """Delete a record or table.

        Args:
            table_or_record_id: The table or record ID to delete.

        Returns:
            A list of dictionaries containing the deleted records.
        """
        response = await self._send("delete", table_or_record_id)
        return response
