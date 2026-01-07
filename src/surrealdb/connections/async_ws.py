"""
A basic async connection to a SurrealDB instance.
"""

import asyncio
from asyncio import AbstractEventLoop, Future, Queue, Task
from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any, Optional, Union
from uuid import UUID

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from surrealdb.connections.async_template import AsyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Value


class AsyncWsSurrealConnection(AsyncTemplate, UtilsMixin):
    """
    A single async connection to a SurrealDB instance. To be used once and discarded.

    Attributes:
        url: The URL of the database to process queries for.
    """

    def __init__(
        self,
        url: str,
    ) -> None:
        """
        The constructor for the AsyncSurrealConnection class.

        :param url: The URL of the database to process queries for.
        """
        self.url: Url = Url(url)
        self.raw_url: str = f"{self.url.raw_url}/rpc"
        self.host: Optional[str] = self.url.hostname
        self.port: Optional[int] = self.url.port
        self.token: Optional[str] = None
        self.socket: Any = None  # WebSocket connection
        self.loop: Optional[AbstractEventLoop] = None
        self.qry: dict[str, Future[dict[str, Any]]] = {}
        self.recv_task: Optional[Task[None]] = None
        self.live_queues: dict[str, list[Queue[dict[str, Any]]]] = {}

    async def _recv_task(self) -> None:
        assert self.socket
        try:
            async for data in self.socket:
                response = decode(data)
                if response_id := response.get("id"):
                    if fut := self.qry.get(response_id):
                        fut.set_result(response)
                elif response_result := response.get("result"):
                    live_id = str(response_result["id"])
                    for queue in self.live_queues.get(live_id, []):
                        queue.put_nowait(response_result)
                else:
                    self.check_response_for_error(response, "_recv_task")
        except (ConnectionClosed, WebSocketException, asyncio.CancelledError):
            # Connection was closed or cancelled, this is expected
            pass
        except Exception as e:
            # Log unexpected errors but don't let them propagate
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Unexpected error in _recv_task: {e}")
        finally:
            # Clean up any pending futures
            for fut in self.qry.values():
                if not fut.done():
                    fut.cancel()
            self.qry.clear()

    async def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        await self.connect()
        assert (
            self.socket is not None and self.loop is not None
        )  # will always not be None as the self.connect ensures there's a connection

        # setup future to wait for response
        fut = self.loop.create_future()
        query_id = message.id
        self.qry[query_id] = fut
        try:
            # correlate message to query, send and forget it
            await self.socket.send(message.WS_CBOR_DESCRIPTOR)
            del message

            # wait for response
            response = await fut
        finally:
            del self.qry[query_id]

        if bypass is False:
            self.check_response_for_error(response, process)

        # Response comes from Future[dict[str, Any]] defined in self.qry
        # The decode() function returns Any, but we know it's always a dict in this context
        if not isinstance(response, dict):
            # This should never happen in practice, but handle defensively
            return {}
        # Return type is dict[str, Any] - contents are dynamic database responses
        # Cannot be more specific without runtime schema validation
        return response

    async def connect(self, url: Optional[str] = None) -> None:
        if self.socket:
            return

        # overwrite params if passed in
        if url is not None:
            self.url = Url(url)
            self.raw_url = f"{self.url.raw_url}/rpc"
            self.host = self.url.hostname
            self.port = self.url.port

        self.socket = await websockets.connect(
            self.raw_url,
            max_size=None,
            subprotocols=[websockets.Subprotocol("cbor")],
        )
        self.loop = asyncio.get_running_loop()
        self.recv_task = asyncio.create_task(self._recv_task())

    async def authenticate(self, token: str) -> None:
        message = RequestMessage(RequestMethod.AUTHENTICATE, token=token)
        await self._send(message, "authenticating")

    async def invalidate(self) -> None:
        message = RequestMessage(RequestMethod.INVALIDATE)
        await self._send(message, "invalidating")
        self.token = None

    async def signup(self, vars: dict[str, Value]) -> str:
        message = RequestMessage(RequestMethod.SIGN_UP, data=vars)
        response = await self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        return response["result"]

    async def signin(self, vars: dict[str, Value]) -> str:
        message = RequestMessage(
            RequestMethod.SIGN_IN,
            username=vars.get("username"),
            password=vars.get("password"),
            access=vars.get("access"),
            database=vars.get("database"),
            namespace=vars.get("namespace"),
            variables=vars.get("variables"),
        )
        response = await self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        self.token = response["result"]
        return response["result"]

    async def info(self) -> Value:
        message = RequestMessage(RequestMethod.INFO)
        response = await self._send(
            message, "getting database information", bypass=True
        )
        self.check_response_for_result(response, "getting auth information")
        return response["result"]

    async def use(self, namespace: str, database: str) -> None:
        message = RequestMessage(
            RequestMethod.USE,
            namespace=namespace,
            database=database,
        )
        await self._send(message, "use")

    async def query(self, query: str, vars: Optional[dict[str, Value]] = None) -> Value:
        response = await self.query_raw(query, vars)
        self.check_response_for_error(response, "query")
        self.check_response_for_result(response, "query")
        return response["result"][0]["result"]

    async def query_raw(
        self, query: str, params: Optional[dict[str, Value]] = None
    ) -> dict[str, Any]:
        if params is None:
            params = {}
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=params,
        )
        response = await self._send(message, "query", bypass=True)
        return response

    async def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        response = await self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    async def let(self, key: str, value: Value) -> None:
        message = RequestMessage(RequestMethod.LET, key=key, value=value)
        await self._send(message, "letting")

    async def unset(self, key: str) -> None:
        message = RequestMessage(RequestMethod.UNSET, params=[key])
        await self._send(message, "unsetting")

    async def select(self, record: RecordIdType) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "select")
        return response["result"][0]["result"]

    async def create(
        self,
        record: RecordIdType,
        data: Optional[Value] = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"CREATE {resource_ref}"
        else:
            variables["_content"] = data
            query = f"CREATE {resource_ref} CONTENT $_content"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "create")
        result = response["result"][0]["result"]
        # CREATE always creates a single record, so always unwrap
        return self._unwrap_result(result, unwrap=True)

    async def update(self, record: RecordIdType, data: Optional[Value] = None) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref}"
        else:
            variables["_content"] = data
            query = f"UPDATE {resource_ref} CONTENT $_content"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "update")
        result = response["result"][0]["result"]
        # UPDATE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def merge(self, record: RecordIdType, data: Optional[Value] = None) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref} MERGE {{}}"
        else:
            variables["_data"] = data
            query = f"UPDATE {resource_ref} MERGE $_data"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "merge")
        result = response["result"][0]["result"]
        # MERGE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def patch(self, record: RecordIdType, data: Optional[Value] = None) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref} PATCH []"
        else:
            variables["_patches"] = data
            query = f"UPDATE {resource_ref} PATCH $_patches"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "patch")
        result = response["result"][0]["result"]
        # PATCH on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def delete(self, record: RecordIdType) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"DELETE {resource_ref} RETURN BEFORE"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "delete")
        result = response["result"][0]["result"]
        # DELETE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def insert(
        self,
        table: Union[str, Table],
        data: Value,
    ) -> Value:
        # Validate that table is not a RecordID
        if isinstance(table, RecordID):
            raise Exception(
                f"There was a problem with the database: Can not execute INSERT statement using value '{table}'"
            )

        variables: dict[str, Any] = {}
        table_ref = self._resource_to_variable(table, variables, "_table")
        variables["_data"] = data
        query = f"INSERT INTO {table_ref} $_data"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "insert")
        return response["result"][0]["result"]

    async def insert_relation(
        self,
        table: Union[str, Table],
        data: Value,
    ) -> Value:
        variables: dict[str, Any] = {}
        table_ref = self._resource_to_variable(table, variables, "_table")
        variables["_data"] = data
        query = f"INSERT RELATION INTO {table_ref} $_data"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "insert_relation")
        return response["result"][0]["result"]

    async def live(self, table: Union[str, Table], diff: bool = False) -> UUID:
        message = RequestMessage(
            RequestMethod.LIVE,
            table=table,
        )
        response = await self._send(message, "live")
        self.check_response_for_result(response, "live")
        uuid = response["result"]
        assert uuid not in self.live_queues
        self.live_queues[str(uuid)] = []
        return uuid

    async def subscribe_live(
        self, query_uuid: Union[str, UUID]
    ) -> AsyncGenerator[dict[str, Value], None]:
        result_queue: Queue[dict[str, Any]] = Queue()
        suid = str(query_uuid)

        # Auto-register if not already registered
        if suid not in self.live_queues:
            self.live_queues[suid] = []

        self.live_queues[suid].append(result_queue)

        async def _iter() -> AsyncGenerator[dict[str, Any], None]:
            while True:
                ret = await result_queue.get()
                yield ret["result"]

        return _iter()

    async def kill(self, query_uuid: Union[str, UUID]) -> None:
        message = RequestMessage(RequestMethod.KILL, uuid=query_uuid)
        await self._send(message, "kill")
        self.live_queues.pop(str(query_uuid), None)

    async def upsert(self, record: RecordIdType, data: Optional[Value] = None) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPSERT {resource_ref}"
        else:
            variables["_content"] = data
            query = f"UPSERT {resource_ref} CONTENT $_content"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "upsert")
        result = response["result"][0]["result"]
        # UPSERT on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def close(self) -> None:
        # Cancel the receive task first
        if self.recv_task and not self.recv_task.done():
            self.recv_task.cancel()
            try:
                await self.recv_task
            except asyncio.CancelledError:
                pass
            except Exception:
                # Ignore any other exceptions during cleanup
                pass

        # Close the WebSocket connection
        if self.socket is not None:
            try:
                await self.socket.close()
            except Exception:
                # Ignore exceptions during socket closure
                pass
            finally:
                self.socket = None
                self.recv_task = None

    async def __aenter__(self) -> "AsyncWsSurrealConnection":
        """
        Asynchronous context manager entry.
        Initializes a websocket connection and returns the connection instance.
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """
        Asynchronous context manager exit.
        Closes the websocket connection upon exiting the context.
        """
        await self.close()
