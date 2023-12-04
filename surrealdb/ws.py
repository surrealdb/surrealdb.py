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

import json
from types import TracebackType
from typing import Any, Dict, List, Optional, Type, Union, Tuple
import websockets
import asyncio
from pydantic import BaseModel, Field, validator
from .common import SurrealException, generate_uuid

__all__ = (
    "Surreal",
    "Request",
    "Response",
    "LiveStream",
)


# ------------------------------------------------------------------------
# Connections


class Request(BaseModel):
    """Represents an RPC request to a Surreal server.

    Attributes:
        id: The ID of the request.
        method: The method of the request.
        params: The parameters of the request.
    """

    id: str = Field(default_factory=generate_uuid)
    method: str
    params: Optional[Tuple] = None

    @validator("params", pre=True, always=True)
    def validate_params(cls, value):  # pylint: disable=no-self-argument
        """Validate the parameters of the request."""
        if value is None:
            return tuple()
        return value

    class Config:
        """Represents the configuration of the RPC request."""

        allow_mutation = False


class Response(BaseModel):
    """Represents a successful RPC response from a Surreal server.

    Attributes:
        id: The ID of the request.
        result: The result of the request.
    """

    id: Optional[str]  # missing for live query responses
    result: Any

    class Config:
        """Represents the configuration of the RPC request.

        Attributes:
            allow_mutation: Whether to allow mutation.
        """

        allow_mutation = False


class ResponseError(BaseModel):
    """Represents an RPC error.

    Attributes:
        code: The code of the error.
        message: The message of the error.
    """

    code: int
    message: str

    class Config:
        """Represents the configuration of the RPC request.

        Attributes:
            allow_mutation: Whether to allow mutation.
        """

        allow_mutation = False


# ------------------------------------------------------------------------
# Websocket Connection


class WebSocketConnection:
    """Represents a websocket connection to a Surreal server."""

    def __init__(
        self,
    ) -> None:
        self.ws: Optional[websockets.WebSocketClientProtocol] = None  # type: ignore
        self.routes: Dict[int, asyncio.Queue] = {}
        self.live_queries: Dict[str, asyncio.Queue] = {}

    async def connect(self, address: str, capacity: int = 0) -> None:
        """Connect to a Surreal server.

        Args:
            address: The address of the Surreal server.
            capacity: The capacity of the Surreal server.
        """
        self.router_queue = asyncio.Queue(capacity)
        self.ws = await websockets.connect(address)
        asyncio.create_task(self._router())

    async def close(self) -> None:
        """Close the connection to the Surreal server."""
        await self.ws.close()

    async def _router(self) -> None:
        """Handle incoming websocket messages and redistribute them as needed."""
        while True:
            try:
                message = await self.ws.recv()
                response = json.loads(message)
                if response.get("id"):
                    await self.routes.pop(response["id"]).put(message)
                else:
                    await self.live_queries.get(response["result"]["id"]).put(message)
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                raise e

    async def send_receive(self, request: Request) -> Response:
        """Send a request to the Surreal server and receive a response."""
        chan = await self.send(request)
        return await self.recv(chan)

    async def send(self, request: Request) -> None:
        """Send a request to the Surreal server.

        Args:
            request: The request to send.

        Raises:
            Exception: If the client is not connected to the Surreal server.
        """
        if request.method == "kill":
            self.live_queries.pop(request.params[0])
        response_chan = asyncio.Queue(maxsize=1)
        self.routes[request.id] = response_chan

        await self.ws.send(json.dumps(request.dict(), ensure_ascii=False))
        return response_chan

    def listen_live(self, query_id: str) -> None:
        """Track a live query.

        Args:
            query_id: The ID of the live query.
        """
        live_channel = asyncio.Queue()
        self.live_queries[query_id] = live_channel
        return live_channel

    async def recv(
        self, queue_channel: asyncio.Queue
    ) -> Union[Response, ResponseError]:
        """Receive a response from the Surreal server.

        Returns:
            The response from the Surreal server.

        Raises:
            Exception: If the client is not connected to the Surreal server.
            Exception: If the response contains an error.
        """
        response = json.loads(await queue_channel.get())
        if response.get("error"):
            parsed_response = ResponseError(**response["error"])
            raise SurrealException(parsed_response.message)
        return Response(**response)


# ------------------------------------------------------------------------
# Live Stream Manager


class LiveStream:
    def __init__(self, client: Surreal, request: Request):
        self.client = client
        self.request = request
        self.response_channel: Optional[asyncio.Queue] = None

    async def __aenter__(self):
        # Setup connection and get query ID
        if self.request.method == "live":
            # then use traditional live path
            response = await self.client.connection.send_receive(self.request)
            self.query_id = response.result
        else:
            # then we are doing a custom live query
            response = await self.client.connection.send_receive(self.request)
            self.query_id = response.result[0]["result"]

        self.response_channel = self.client.connection.listen_live(self.query_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Teardown connection using query ID
        if self.query_id:
            await self.client.connection.send_receive(
                Request(method="kill", params=(self.query_id,))
            )
        self.response_channel = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.response_channel is None:
            raise StopAsyncIteration
        return await self.response_channel.get()


# ------------------------------------------------------------------------
# Surreal library methods - exposed to user


class Surreal:
    """Surreal is a class that represents a Surreal server.

    Args:
        url: The URL of the Surreal server.

    Examples:
        Connect to a local endpoint
            db = Surreal('ws://127.0.0.1:8000/rpc')
            await db.connect()
            await db.signin({"user": "root", "pass": "root"})

        Connect to a remote endpoint
            db = Surreal('ws://cloud.surrealdb.com/rpc')
            await db.connect()
            await db.signin({"user": "root", "pass": "root"})

        Connect with a context manager
            async with Surreal("ws://127.0.0.1:8000/rpc") as db:
                await db.signin({"user": "root", "pass": "root"})

    """

    def __init__(self, url: str) -> None:
        self.url = url
        self.token: Optional[str] = None
        self.connection: WebSocketConnection = WebSocketConnection()

    async def connect(self) -> None:
        await self.connection.connect(self.url)
        return self

    async def __aenter__(self) -> Surreal:
        """Create a connection when entering the context manager.

        Returns:
            The Surreal client.
        """
        return await self.connect()

    async def close(self) -> None:
        """Close the connection to the Surreal server."""
        await self.connection.close()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[Type[BaseException]] = None,
        traceback: Optional[Type[TracebackType]] = None,
    ) -> None:
        """Close the connection when exiting the context manager.

        Args:
            exc_type: The type of the exception.
            exc_value: The value of the exception.
            traceback: The traceback of the exception.
        """
        return await self.close()

    async def use(self, namespace: str, database: str) -> None:
        """Switch to a specific namespace and database.

        Args:
            namespace: Switches to a specific namespace.
            database: Switches to a specific database.

        Examples:
            await db.use('test', 'test')
        """
        response = await self.connection.send_receive(
            Request(method="use", params=(namespace, database)),
        )

    async def signup(self, vars: Dict[str, Any]) -> str:
        """Sign this connection up to a specific authentication scope.

        Args:
            vars: Variables used in a signup query.

        Examples:
            await db.signup({"user": "bob", "pass": "123456"})
        """
        response = await self.connection.send_receive(
            Request(method="signup", params=(vars,)),
        )
        token: str = response.result
        self.token = token
        return self.token

    async def signin(self, vars: Dict[str, Any]) -> str:
        """Sign this connection in to a specific authentication scope.

        Args:
            vars: Variables used in a signin query.

        Examples:
            await db.signin({"user": "root", "pass": "root"})
        """
        response = await self.connection.send_receive(
            Request(method="signin", params=(vars,)),
        )
        token: str = response.result
        self.token = token
        return self.token

    async def invalidate(self) -> None:
        """Invalidate the authentication for the current connection."""
        await self.connection.send_receive(
            Request(
                method="invalidate",
            ),
        )
        self.token = None

    async def authenticate(self, token: str) -> None:
        """Authenticate the current connection with a JWT token.

        Args:
            token: The token to use for the connection.

        Examples:
            await db.authenticate('JWT token here')
        """
        await self.connection.send_receive(
            Request(method="authenticate", params=(token,)),
        )

    async def let(self, key: str, value: Any) -> None:
        """Assign a value as a parameter for this connection.

        Args:
            key: Specifies the name of the variable.
            value: Assigns the value to the variable name.

        Examples:
            await db.let("name", {
                "first": "Tobie",
                "last": "Morgan Hitchcock",
            })

            Use the variable in a subsequent query
                await db.query('create person set name = $name')
        """
        response = await self.connection.send_receive(
            Request(
                method="let",
                params=(
                    key,
                    value,
                ),
            ),
        )
        return response.result

    async def set(self, key: str, value: Any) -> None:
        """Alias for `let`. Assigns a value as a parameter for this connection.

        Args:
            key: Specifies the name of the variable.
            value: Assigns the value to the variable name.
        """
        response = await self.connection.send_receive(
            Request(
                method="let",
                params=(
                    key,
                    value,
                ),
            ),
        )
        return response.result

    async def query(
        self, sql: str, vars: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Run a set of SurrealQL statements against the database.

        Args:
            sql: Specifies the SurrealQL statements.
            vars: Assigns variables which can be used in the query.

        Returns:
            The records.

        Examples:
            Assign the variable on the connection
                result = await db.query('create person; select * from type::table($tb)', {'tb': 'person'})

            Get the first result from the first query
                result[0]['result'][0]

            Get all of the results from the second query
                result[1]['result']
        """
        response = await self.connection.send_receive(
            Request(
                method="query",
                params=(sql,) if vars is None else (sql, vars),
            ),
        )
        return response.result

    async def select(self, thing: str) -> List[Dict[str, Any]]:
        """Select all records in a table (or other entity),
        or a specific record, in the database.

        This function will run the following query in the database:
        select * from $thing

        Args:
            thing: The table or record ID to select.

        Returns:
            The records.

        Examples:
            Select all records from a table (or other entity)
                people = await db.select('person')

            Select a specific record from a table (or other entity)
                person = await db.select('person:h5wxrf2ewk8xjxosxtyc')
        """
        response = await self.connection.send_receive(
            Request(method="select", params=(thing,)),
        )
        return response.result

    async def create(
        self, thing: str, data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Create a record in the database.

        This function will run the following query in the database:
        create $thing content $data

        Args:
            thing: The table or record ID.
            data: The document / record data to insert.

        Examples:
            Create a record with a random ID
                person = await db.create('person')

            Create a record with a specific ID
                record = await db.create('person:tobie', {
                    'name': 'Tobie',
                    'settings': {
                        'active': true,
                        'marketing': true,
                        },
                })
        """
        response = await self.connection.send_receive(
            Request(
                method="create",
                params=(thing,) if data is None else (thing, data),
            ),
        )
        return response.result

    async def update(
        self, thing: str, data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Update all records in a table, or a specific record, in the database.

        This function replaces the current document / record data with the
        specified data.

        This function will run the following query in the database:
        update $thing content $data

        Args:
            thing: The table or record ID.
            data: The document / record data to insert.

        Examples:
            Update all records in a table
                person = await db.update('person')

            Update a record with a specific ID
                record = await db.update('person:tobie', {
                    'name': 'Tobie',
                    'settings': {
                        'active': true,
                        'marketing': true,
                        },
                })
        """
        response = await self.connection.send_receive(
            Request(
                method="update",
                params=(thing,) if data is None else (thing, data),
            ),
        )
        return response.result

    async def merge(
        self, thing: str, data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Modify by deep merging all records in a table, or a specific record, in the database.

        This function merges the current document / record data with the
        specified data.

        This function will run the following query in the database:
        update $thing merge $data

        Args:
            thing: The table name or the specific record ID to change.
            data: The document / record data to insert.

        Examples:
            Update all records in a table
                people = await db.merge('person', {
                    'updated_at':  str(datetime.datetime.utcnow())
                    })

            Update a record with a specific ID
                person = await db.merge('person:tobie', {
                    'updated_at': str(datetime.datetime.utcnow()),
                    'settings': {
                        'active': True,
                        },
                    })

        """
        response = await self.connection.send_receive(
            Request(
                method="change",
                params=(thing,) if data is None else (thing, data),
            ),
        )
        return response.result

    async def patch(
        self, thing: str, data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply JSON Patch changes to all records, or a specific record, in the database.

        This function patches the current document / record data with
        the specified JSON Patch data.

        This function will run the following query in the database:
        update $thing patch $data

        Args:
            thing: The table or record ID.
            data: The data to modify the record with.

        Examples:
            Update all records in a table
                people = await db.patch('person', [
                    { 'op': "replace", 'path': "/created_at", 'value': str(datetime.datetime.utcnow()) }])

            Update a record with a specific ID
            person = await db.patch('person:tobie', [
                { 'op': "replace", 'path': "/settings/active", 'value': False },
                { 'op': "add", "path": "/tags", "value": ["developer", "engineer"] },
                { 'op': "remove", "path": "/temp" },
            ])
        """
        response = await self.connection.send_receive(
            Request(
                method="modify",
                params=(thing,) if data is None else (thing, data),
            ),
        )
        return response.result

    async def delete(self, thing: str) -> List[Dict[str, Any]]:
        """Delete all records in a table, or a specific record, from the database.

        This function will run the following query in the database:
        delete * from $thing

        Args:
            thing: The table name or a record ID to delete.

        Examples:
            Delete all records from a table
                await db.delete('person')
            Delete a specific record from a table
                await db.delete('person:h5wxrf2ewk8xjxosxtyc')
        """
        response = await self.connection.send_receive(
            Request(method="delete", params=(thing,)),
        )
        return response.result

    # ------------------------------------------------------------------------
    # Surreal library methods - undocumented but implemented in js library

    async def info(self) -> Optional[Dict[str, Any]]:
        """Retrieve info about the current Surreal instance.

        Returns:
            The information of the Surreal server.
        """
        response = await self.connection.send_receive(
            Request(
                method="info",
            ),
        )
        return response.result

    def live(self, table: str, diff=False) -> LiveStream:
        """Get a live stream of changes to a table.

        Args:
            table: The table name.

        Returns:
            Live Stream Manager for accessing records

        Examples:
            Get a live stream of changes to a table
                async with db.live("person") as stream:
                    async for record in stream:
                        print(record)
        """
        return LiveStream(self, Request(method="live", params=(table, diff)))

    def live_query(self, sql: str, vars: Optional[Dict[str, Any]] = None) -> LiveStream:
        """Get a live stream of changes to a query.

        Args:
            query: The query.

        Returns:
            Live Stream Manager for accessing records

        Examples:
            Get a live stream of changes to a query
                async with db.live_query("LIVE SELECT * FROM person") as stream:
                    async for record in stream:
                        print(record)
        """

        return LiveStream(
            self,
            Request(
                method="query",
                params=(sql,) if vars is None else (sql, vars),
            ),
        )

    async def ping(self) -> bool:
        """Ping the Surreal server."""
        response = await self.connection.send_receive(
            Request(
                method="ping",
            ),
        )
        return response.result

    async def kill(self, query: str) -> None:
        """Kill a specific query.

        Args:
            query: The query to kill.
        """
        response = await self.connection.send_receive(
            Request(method="kill", params=(query,)),
        )
        return response.result
