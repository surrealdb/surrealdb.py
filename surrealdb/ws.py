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

import enum
import json
import uuid
from types import TracebackType
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import pydantic
import websockets

__all__ = ("Surreal",)

# ------------------------------------------------------------------------
# ID


def generate_uuid() -> str:
    """Generate a UUID.

    Returns:
        A UUID as a string.
    """
    return str(uuid.uuid4())


# ------------------------------------------------------------------------
# Exceptions
class SurrealException(Exception):
    """Base exception for SurrealDB client library."""


class SurrealAuthenticationException(SurrealException):
    """Exception raised for errors with the SurrealDB authentication."""


class SurrealPermissionException(SurrealException):
    """Exception raised for errors with the SurrealDB permissions."""


# ------------------------------------------------------------------------
# Connections


class ConnectionState(enum.Enum):
    """Represents the state of the connection.

    Attributes:
        CONNECTING: The connection is in progress.
        CONNECTED:  The connection is established.
        DISCONNECTED: The connection is closed.
    """

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2


class Request(pydantic.BaseModel):
    """Represents an RPC request to a Surreal server.

    Attributes:
        id: The ID of the request.
        method: The method of the request.
        params: The parameters of the request.
    """

    id: str
    method: str
    params: Optional[Tuple] = None

    @pydantic.validator("params", pre=True, always=True)
    def validate_params(cls, value):  # pylint: disable=no-self-argument
        """Validate the parameters of the request."""
        if value is None:
            return tuple()
        return value

    class Config:
        """Represents the configuration of the RPC request."""

        frozen = True


class ResponseSuccess(pydantic.BaseModel):
    """Represents a successful RPC response from a Surreal server.

    Attributes:
        id: The ID of the request.
        result: The result of the request.
    """

    id: Optional[str] = None
    result: Any

    class Config:
        """Represents the configuration of the RPC request.

        Attributes:
            frozen: Whether to prohibit mutation.
        """

        frozen = True


class ResponseError(pydantic.BaseModel):
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
            frozen: Whether to prohibit mutation.
        """

        frozen = True


def _validate_response(
    response: Union[ResponseSuccess, ResponseError],
    exception: Type[Exception] = SurrealException,
) -> ResponseSuccess:
    """Validate the response.
    The response is validated by checking if it is an error. If it is an error,
    the exception is raised. Otherwise, the response is returned.

    Args:
        response: The response to validate.
        exception: The exception to raise if the response is an error.

    Returns:
        The original response.

    Raises:
        SurrealDBException: If the response is an error.
    """
    if isinstance(response, ResponseError):
        raise exception(response.message)
    return response


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

    def __init__(self, url: str, max_size: Optional[int] = 2**20) -> None:
        self.url = url
        self.max_size = max_size
        self.client_state = ConnectionState.CONNECTING
        self.token: Optional[str] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None  # type: ignore

    async def __aenter__(self) -> Surreal:
        """Create a connection when entering the context manager.

        Returns:
            The Surreal client.
        """
        await self.connect()
        return self

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
        await self.close()

    async def connect(self) -> None:
        """Connect to a local or remote database endpoint."""
        self.ws = await websockets.connect(self.url)  # type: ignore
        self.client_state = ConnectionState.CONNECTED

    async def close(self) -> None:
        """Close the persistent connection to the database."""
        await self.ws.close()
        self.client_state = ConnectionState.DISCONNECTED

    async def use(self, namespace: str, database: str) -> None:
        """Switch to a specific namespace and database.

        Args:
            namespace: Switches to a specific namespace.
            database: Switches to a specific database.

        Examples:
            await db.use('test', 'test')
        """
        response = await self._send_receive(
            Request(id=generate_uuid(), method="use", params=(namespace, database)),
        )
        _validate_response(response)

    async def signup(self, vars: Dict[str, Any]) -> str:
        """Sign this connection up to a specific authentication scope.

        Args:
            vars: Variables used in a signup query.

        Examples:
            await db.signup({"user": "bob", "pass": "123456"})
        """
        response = await self._send_receive(
            Request(id=generate_uuid(), method="signup", params=(vars,)),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealAuthenticationException
        )
        token: str = success.result
        self.token = token
        return self.token

    async def signin(self, vars: Dict[str, Any]) -> str:
        """Sign this connection in to a specific authentication scope.

        Args:
            vars: Variables used in a signin query.

        Examples:
            await db.signin({"user": "root", "pass": "root"})
        """
        response = await self._send_receive(
            Request(id=generate_uuid(), method="signin", params=(vars,)),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealAuthenticationException
        )
        token: str = success.result
        self.token = token
        return self.token

    async def invalidate(self) -> None:
        """Invalidate the authentication for the current connection."""
        response = await self._send_receive(
            Request(
                id=generate_uuid(),
                method="invalidate",
            ),
        )
        _validate_response(response, SurrealAuthenticationException)
        self.token = None

    async def authenticate(self, token: str) -> None:
        """Authenticate the current connection with a JWT token.

        Args:
            token: The token to use for the connection.

        Examples:
            await db.authenticate('JWT token here')
        """
        response = await self._send_receive(
            Request(id=generate_uuid(), method="authenticate", params=(token,)),
        )
        _validate_response(response, SurrealAuthenticationException)

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
        response = await self._send_receive(
            Request(
                id=generate_uuid(),
                method="let",
                params=(
                    key,
                    value,
                ),
            ),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealPermissionException
        )
        return success.result

    async def set(self, key: str, value: Any) -> None:
        """Alias for `let`. Assigns a value as a parameter for this connection.

        Args:
            key: Specifies the name of the variable.
            value: Assigns the value to the variable name.
        """
        response = await self._send_receive(
            Request(
                id=generate_uuid(),
                method="let",
                params=(
                    key,
                    value,
                ),
            ),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealPermissionException
        )
        return success.result

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
        response = await self._send_receive(
            Request(
                id=generate_uuid(),
                method="query",
                params=(sql,) if vars is None else (sql, vars),
            ),
        )
        success: ResponseSuccess = _validate_response(response)
        return success.result

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
        response = await self._send_receive(
            Request(id=generate_uuid(), method="select", params=(thing,)),
        )
        success: ResponseSuccess = _validate_response(response)
        return success.result

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
        response = await self._send_receive(
            Request(
                id=generate_uuid(),
                method="create",
                params=(thing,) if data is None else (thing, data),
            ),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealPermissionException
        )
        return success.result

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
        response = await self._send_receive(
            Request(
                id=generate_uuid(),
                method="update",
                params=(thing,) if data is None else (thing, data),
            ),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealPermissionException
        )
        return success.result

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
        response = await self._send_receive(
            Request(
                id=generate_uuid(),
                method="merge",
                params=(thing,) if data is None else (thing, data),
            ),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealPermissionException
        )
        return success.result

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
        response = await self._send_receive(
            Request(
                id=generate_uuid(),
                method="modify",
                params=(thing,) if data is None else (thing, data),
            ),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealPermissionException
        )
        return success.result

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
        response = await self._send_receive(
            Request(id=generate_uuid(), method="delete", params=(thing,)),
        )
        success: ResponseSuccess = _validate_response(
            response, SurrealPermissionException
        )
        return success.result

    async def live(self, table: str, diff: bool = False) -> str:
        """Initiates a live query.

        Args:
            table: The table name to listen for changes for.
            diff: If set to true, live notifications will include
                an array of JSON Patch objects,
                rather than the entire record for each notification.

        Returns:
            UUID string.
        """
        response = await self._send_receive(
            Request(id=generate_uuid(), method="live", params=(table, diff)),
        )
        success: ResponseSuccess = _validate_response(response)
        return success.result

    async def kill(self, query_uuid: str) -> None:
        """Kills a running live query by it's UUID.

        Args:
            query_uuid: The UUID of the live query you wish to kill.
        """
        response = await self._send_receive(
            Request(id=generate_uuid(), method="kill", params=(query_uuid,)),
        )
        success: ResponseSuccess = _validate_response(response)
        return success.result

    # ------------------------------------------------------------------------
    # Send & Receive methods

    async def _send_receive(
        self, request: Request
    ) -> Union[ResponseSuccess, ResponseError]:
        """Send a request to the Surreal server and receive a response.

        Args:
            request: The request to send.

        Returns:
            The response from the Surreal server.

        Raises:
            Exception: If the client is not connected to the Surreal server.
        """
        await self._send(request)
        return await self._recv()

    async def _send(self, request: Request) -> None:
        """Send a request to the Surreal server.

        Args:
            request: The request to send.

        Raises:
            Exception: If the client is not connected to the Surreal server.
        """
        self._validate_connection()
        await self.ws.send(json.dumps(request.dict(), ensure_ascii=False))

    async def _recv(self) -> Union[ResponseSuccess, ResponseError]:
        """Receive a response from the Surreal server.

        Returns:
            The response from the Surreal server.

        Raises:
            Exception: If the client is not connected to the Surreal server.
            Exception: If the response contains an error.
        """
        self._validate_connection()
        response = json.loads(await self.ws.recv())
        if response.get("error"):
            return ResponseError(**response["error"])
        return ResponseSuccess(**response)

    def _validate_connection(self) -> None:
        """Validate the connection to the Surreal server."""
        if self.client_state != ConnectionState.CONNECTED:
            raise SurrealException("Not connected to Surreal server.")
