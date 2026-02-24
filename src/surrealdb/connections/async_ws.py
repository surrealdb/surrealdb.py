"""
A basic async connection to a SurrealDB instance.
"""

import asyncio
import uuid
from asyncio import AbstractEventLoop, Future, Queue, Task
from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any
from uuid import UUID

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from surrealdb.connections.async_template import AsyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import SurrealError, UnexpectedResponseError
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Tokens, Value, parse_auth_result


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
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.token: str | None = None
        self.socket: Any = None  # WebSocket connection
        self.loop: AbstractEventLoop | None = None
        self.qry: dict[str, Future[dict[str, Any]]] = {}
        self.recv_task: Task[None] | None = None
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

    async def connect(self, url: str | None = None) -> None:
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

    async def authenticate(self, token: str, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"token": token}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.AUTHENTICATE, **kwargs)
        await self._send(message, "authenticating")

    async def invalidate(self, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INVALIDATE, **kwargs)
        await self._send(message, "invalidating")
        self.token = None

    async def signup(
        self, vars: dict[str, Value], session_id: UUID | None = None
    ) -> Tokens:
        kwargs: dict[str, Any] = {"data": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_UP, **kwargs)
        response = await self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    async def signin(
        self, vars: dict[str, Value], session_id: UUID | None = None
    ) -> Tokens:
        kwargs: dict[str, Any] = {"params": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_IN, **kwargs)
        response = await self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    async def info(self, session_id: UUID | None = None) -> Value:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INFO, **kwargs)
        response = await self._send(
            message, "getting database information", bypass=True
        )
        self.check_response_for_result(response, "getting auth information")
        return response["result"]

    async def use(
        self,
        namespace: str,
        database: str,
        session_id: UUID | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "namespace": namespace,
            "database": database,
        }
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.USE, **kwargs)
        await self._send(message, "use")

    async def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        response = await self.query_raw(
            query, vars, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "query")
        self.check_response_for_result(response, "query")
        self._check_query_result(response["result"][0])
        return response["result"][0]["result"]

    async def query_raw(
        self,
        query: str,
        params: dict[str, Value] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> dict[str, Any]:
        if params is None:
            params = {}
        kwargs: dict[str, Any] = {"query": query, "params": params}
        if session_id is not None:
            kwargs["session"] = session_id
        if txn_id is not None:
            kwargs["txn"] = txn_id
        message = RequestMessage(RequestMethod.QUERY, **kwargs)
        response = await self._send(message, "query", bypass=True)
        return response

    async def version(self, session_id: UUID | None = None) -> str:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.VERSION, **kwargs)
        response = await self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    async def let(
        self,
        key: str,
        value: Value,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"key": key, "value": value}
        if session_id is not None:
            kwargs["session"] = session_id
        if txn_id is not None:
            kwargs["txn"] = txn_id
        message = RequestMessage(RequestMethod.LET, **kwargs)
        await self._send(message, "letting")

    async def unset(
        self,
        key: str,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"params": [key]}
        if session_id is not None:
            kwargs["session"] = session_id
        if txn_id is not None:
            kwargs["txn"] = txn_id
        message = RequestMessage(RequestMethod.UNSET, **kwargs)
        await self._send(message, "unsetting")

    async def select(
        self,
        record: RecordIdType,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "select")
        self._check_query_result(response["result"][0])
        return response["result"][0]["result"]

    async def create(
        self,
        record: RecordIdType,
        data: Value | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"CREATE {resource_ref}"
        else:
            variables["_content"] = data
            query = f"CREATE {resource_ref} CONTENT $_content"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "create")
        self._check_query_result(response["result"][0])
        result = response["result"][0]["result"]
        # CREATE always creates a single record, so always unwrap
        return self._unwrap_result(result, unwrap=True)

    async def update(
        self,
        record: RecordIdType,
        data: Value | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref}"
        else:
            variables["_content"] = data
            query = f"UPDATE {resource_ref} CONTENT $_content"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "update")
        self._check_query_result(response["result"][0])
        result = response["result"][0]["result"]
        # UPDATE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def merge(
        self,
        record: RecordIdType,
        data: Value | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref} MERGE {{}}"
        else:
            variables["_data"] = data
            query = f"UPDATE {resource_ref} MERGE $_data"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "merge")
        self._check_query_result(response["result"][0])
        result = response["result"][0]["result"]
        # MERGE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def patch(
        self,
        record: RecordIdType,
        data: Value | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref} PATCH []"
        else:
            variables["_patches"] = data
            query = f"UPDATE {resource_ref} PATCH $_patches"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "patch")
        self._check_query_result(response["result"][0])
        result = response["result"][0]["result"]
        # PATCH on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def delete(
        self,
        record: RecordIdType,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"DELETE {resource_ref} RETURN BEFORE"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "delete")
        self._check_query_result(response["result"][0])
        result = response["result"][0]["result"]
        # DELETE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    async def insert(
        self,
        table: str | Table,
        data: Value,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        # Validate that table is not a RecordID
        if isinstance(table, RecordID):
            raise SurrealError(
                f"There was a problem with the database: Can not execute INSERT statement using value '{table}'"
            )

        variables: dict[str, Any] = {}
        table_ref = self._resource_to_variable(table, variables, "_table")
        variables["_data"] = data
        query = f"INSERT INTO {table_ref} $_data"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "insert")
        self._check_query_result(response["result"][0])
        return response["result"][0]["result"]

    async def insert_relation(
        self,
        table: str | Table,
        data: Value,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        table_ref = self._resource_to_variable(table, variables, "_table")
        variables["_data"] = data
        query = f"INSERT RELATION INTO {table_ref} $_data"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "insert_relation")
        self._check_query_result(response["result"][0])
        return response["result"][0]["result"]

    async def live(
        self,
        table: str | Table,
        diff: bool = False,
        session_id: UUID | None = None,
    ) -> UUID:
        kwargs: dict[str, Any] = {"table": table}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.LIVE, **kwargs)
        response = await self._send(message, "live")
        self.check_response_for_result(response, "live")
        uuid = response["result"]
        assert uuid not in self.live_queues
        self.live_queues[str(uuid)] = []
        return uuid

    async def subscribe_live(
        self, query_uuid: str | UUID
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

    async def kill(
        self,
        query_uuid: str | UUID,
        session_id: UUID | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"uuid": query_uuid}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.KILL, **kwargs)
        await self._send(message, "kill")
        self.live_queues.pop(str(query_uuid), None)

    async def attach(self) -> UUID:
        session_id = UUID(str(uuid.uuid4()))
        message = RequestMessage(RequestMethod.ATTACH, session=session_id)
        await self._send(message, "attach")
        return session_id

    async def detach(self, session_id: UUID) -> None:
        message = RequestMessage(RequestMethod.DETACH, session=session_id)
        await self._send(message, "detach")

    async def begin(self, session_id: UUID | None = None) -> UUID:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.BEGIN, **kwargs)
        response = await self._send(message, "begin")
        self.check_response_for_result(response, "begin")
        result = response["result"]
        if isinstance(result, UUID):
            return result
        if isinstance(result, str):
            return UUID(result)
        if isinstance(result, list) and len(result) == 1:
            return UUID(str(result[0]))
        if isinstance(result, dict):
            txn_val = result.get("id") or result.get("txn")
            if txn_val is not None:
                return UUID(str(txn_val))
        raise UnexpectedResponseError(
            f"begin() expected transaction UUID from server, got: {type(result).__name__}"
        )

    async def commit(self, txn_id: UUID, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"txn": txn_id}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.COMMIT, **kwargs)
        await self._send(message, "commit")

    async def cancel(self, txn_id: UUID, session_id: UUID | None = None) -> None:
        if session_id is not None:
            message = RequestMessage(
                RequestMethod.CANCEL, txn=txn_id, session=session_id
            )
        else:
            message = RequestMessage(RequestMethod.CANCEL, txn=txn_id)
        await self._send(message, "cancel")

    async def new_session(self) -> "AsyncSurrealSession":
        session_id = await self.attach()
        return AsyncSurrealSession(self, session_id)

    async def upsert(
        self,
        record: RecordIdType,
        data: Value | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPSERT {resource_ref}"
        else:
            variables["_content"] = data
            query = f"UPSERT {resource_ref} CONTENT $_content"

        response = await self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "upsert")
        self._check_query_result(response["result"][0])
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
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Asynchronous context manager exit.
        Closes the websocket connection upon exiting the context.
        """
        await self.close()


class AsyncSurrealSession:
    def __init__(
        self,
        connection: AsyncWsSurrealConnection,
        session_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id

    async def use(self, namespace: str, database: str) -> None:
        await self._connection.use(namespace, database, session_id=self._session_id)

    async def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> Value:
        return await self._connection.query(query, vars, session_id=self._session_id)

    async def signin(self, vars: dict[str, Value]) -> Tokens:
        return await self._connection.signin(vars, session_id=self._session_id)

    async def signup(self, vars: dict[str, Value]) -> Tokens:
        return await self._connection.signup(vars, session_id=self._session_id)

    async def authenticate(self, token: str) -> None:
        await self._connection.authenticate(token, session_id=self._session_id)

    async def invalidate(self) -> None:
        await self._connection.invalidate(session_id=self._session_id)

    async def let(self, key: str, value: Value) -> None:
        await self._connection.let(key, value, session_id=self._session_id)

    async def unset(self, key: str) -> None:
        await self._connection.unset(key, session_id=self._session_id)

    async def select(self, record: RecordIdType) -> Value:
        return await self._connection.select(record, session_id=self._session_id)

    async def create(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.create(record, data, session_id=self._session_id)

    async def update(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.update(record, data, session_id=self._session_id)

    async def merge(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.merge(record, data, session_id=self._session_id)

    async def patch(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.patch(record, data, session_id=self._session_id)

    async def delete(self, record: RecordIdType) -> Value:
        return await self._connection.delete(record, session_id=self._session_id)

    async def insert(
        self,
        table: str | Table,
        data: Value,
    ) -> Value:
        return await self._connection.insert(table, data, session_id=self._session_id)

    async def insert_relation(
        self,
        table: str | Table,
        data: Value,
    ) -> Value:
        return await self._connection.insert_relation(
            table, data, session_id=self._session_id
        )

    async def upsert(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.upsert(record, data, session_id=self._session_id)

    async def live(
        self,
        table: str | Table,
        diff: bool = False,
    ) -> UUID:
        return await self._connection.live(table, diff, session_id=self._session_id)

    async def kill(self, query_uuid: str | UUID) -> None:
        await self._connection.kill(query_uuid, session_id=self._session_id)

    async def begin_transaction(self) -> "AsyncSurrealTransaction":
        txn_id = await self._connection.begin(session_id=self._session_id)
        return AsyncSurrealTransaction(self._connection, self._session_id, txn_id)

    async def close_session(self) -> None:
        await self._connection.detach(self._session_id)


class AsyncSurrealTransaction:
    def __init__(
        self,
        connection: AsyncWsSurrealConnection,
        session_id: UUID,
        txn_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id
        self._txn_id = txn_id

    async def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> Value:
        return await self._connection.query(
            query,
            vars,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def select(self, record: RecordIdType) -> Value:
        return await self._connection.select(
            record,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def create(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.create(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def update(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.update(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def merge(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.merge(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def patch(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.patch(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def delete(self, record: RecordIdType) -> Value:
        return await self._connection.delete(
            record,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def insert(
        self,
        table: str | Table,
        data: Value,
    ) -> Value:
        return await self._connection.insert(
            table,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def insert_relation(
        self,
        table: str | Table,
        data: Value,
    ) -> Value:
        return await self._connection.insert_relation(
            table,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def upsert(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return await self._connection.upsert(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def commit(self) -> None:
        await self._connection.commit(self._txn_id, session_id=self._session_id)

    async def cancel(self) -> None:
        await self._connection.cancel(self._txn_id, session_id=self._session_id)
