"""
A basic blocking connection to a SurrealDB instance.
"""

import threading
import uuid
from collections.abc import Generator
from types import TracebackType
from typing import Any
from uuid import UUID

import websockets
import websockets.sync.client as ws_sync
from websockets.sync.client import ClientConnection

from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Tokens, Value, parse_auth_result


class BlockingWsSurrealConnection(SyncTemplate, UtilsMixin):
    """
    A single blocking connection to a SurrealDB instance. To be used once and discarded.

    Attributes:
        url: The URL of the database to process queries for.
        user: The username to login on.
        password: The password to login on.
        namespace: The namespace that the connection will stick to.
        database: The database that the connection will stick to.
        id: The ID of the connection.
    """

    def __init__(self, url: str) -> None:
        """
        The constructor for the BlockingWsSurrealConnection class.

        :param url: (str) the URL of the database to process queries for.
        """
        self.url: Url = Url(url)
        self.raw_url: str = f"{self.url.raw_url}/rpc"
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.id: str = str(uuid.uuid4())
        self.token: str | None = None
        self.socket: ClientConnection | None = None
        self._lock: threading.Lock = threading.Lock()

    def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        # Use a lock to ensure thread-safe send/recv operations
        # This prevents race conditions when multiple threads share the same connection
        with self._lock:
            if self.socket is None:
                self.socket = ws_sync.connect(
                    self.raw_url,
                    max_size=None,
                    subprotocols=[websockets.Subprotocol("cbor")],
                )
            self.socket.send(message.WS_CBOR_DESCRIPTOR)
            data = self.socket.recv()
            response = decode(data if isinstance(data, bytes) else data.encode())

            # Verify the response ID matches the request ID
            # Note: Some responses (like live query notifications) may not have an "id" field
            # Only verify if the response has an id field
            response_id = response.get("id")
            if response_id is not None and response_id != message.id:
                raise RuntimeError(
                    f"Response ID mismatch: expected {message.id}, got {response_id}. "
                    "This should not happen with proper locking."
                )

            if bypass is False:
                self.check_response_for_error(response, process)
            return response

    def authenticate(self, token: str, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"token": token}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.AUTHENTICATE, **kwargs)
        self.id = message.id
        self._send(message, "authenticating")

    def invalidate(self, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INVALIDATE, **kwargs)
        self.id = message.id
        self._send(message, "invalidating")
        self.token = None

    def signup(self, vars: dict[str, Value], session_id: UUID | None = None) -> Tokens:
        kwargs: dict[str, Any] = {"data": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_UP, **kwargs)
        self.id = message.id
        response = self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    def signin(self, vars: dict[str, Value], session_id: UUID | None = None) -> Tokens:
        kwargs: dict[str, Any] = {"params": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_IN, **kwargs)
        self.id = message.id
        response = self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    def info(self, session_id: UUID | None = None) -> Value:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INFO, **kwargs)
        self.id = message.id
        response = self._send(message, "getting database information", bypass=True)
        self.check_response_for_result(response, "getting database information")
        return response["result"]

    def use(
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
        self.id = message.id
        self._send(message, "use")

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        response = self.query_raw(query, vars, session_id=session_id, txn_id=txn_id)
        self.check_response_for_error(response, "query")
        self.check_response_for_result(response, "query")
        return response["result"][0]["result"]

    def query_raw(
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
        self.id = message.id
        response = self._send(message, "query", bypass=True)
        return response

    def version(self, session_id: UUID | None = None) -> str:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.VERSION, **kwargs)
        self.id = message.id
        response = self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    def let(
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
        self.id = message.id
        self._send(message, "letting")

    def unset(
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
        self.id = message.id
        self._send(message, "unsetting")

    def select(
        self,
        record: RecordIdType,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "select")
        return response["result"][0]["result"]

    def create(
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

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "create")
        result = response["result"][0]["result"]
        # CREATE always creates a single record, so always unwrap
        return self._unwrap_result(result, unwrap=True)

    def live(
        self,
        table: str | Table,
        diff: bool = False,
        session_id: UUID | None = None,
    ) -> UUID:
        kwargs: dict[str, Any] = {"table": table}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.LIVE, **kwargs)
        self.id = message.id
        response = self._send(message, "live")
        self.check_response_for_result(response, "live")
        return response["result"]

    def kill(
        self,
        query_uuid: str | UUID,
        session_id: UUID | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"uuid": query_uuid}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.KILL, **kwargs)
        self.id = message.id
        self._send(message, "kill")

    def delete(
        self,
        record: RecordIdType,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"DELETE {resource_ref} RETURN BEFORE"

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "delete")
        result = response["result"][0]["result"]
        # DELETE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def insert(
        self,
        table: str | Table,
        data: Value,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
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

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "insert")
        return response["result"][0]["result"]

    def insert_relation(
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

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "insert_relation")
        return response["result"][0]["result"]

    def merge(
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

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "merge")
        result = response["result"][0]["result"]
        # MERGE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def patch(
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

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "patch")
        result = response["result"][0]["result"]
        # PATCH on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def subscribe_live(
        self,
        query_uuid: str | UUID,
    ) -> Generator[dict[str, Value], None, None]:
        """
        Subscribe to live updates for a given query UUID.

        Args:
            query_uuid (Union[str, UUID]): The query UUID to subscribe to.

        Yields:
            dict: The results of live updates.
        """
        try:
            while True:
                try:
                    if self.socket is None:
                        raise ConnectionError(
                            "WebSocket connection is not established."
                        )

                    # Receive a message from the WebSocket
                    data = self.socket.recv()
                    response = decode(
                        data if isinstance(data, bytes) else data.encode()
                    )

                    # Check if the response matches the query UUID
                    if response.get("result", {}).get("id") == query_uuid:
                        yield response["result"]["result"]
                except Exception as e:
                    # Handle WebSocket or decoding errors
                    print("Error in live subscription:", e)
                    yield {"error": str(e)}
        except GeneratorExit:
            # Handle generator exit gracefully if needed
            pass

    def update(
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

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "update")
        result = response["result"][0]["result"]
        # UPDATE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def upsert(
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

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "upsert")
        result = response["result"][0]["result"]
        # UPSERT on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def attach(self) -> UUID:
        session_id = UUID(str(uuid.uuid4()))
        message = RequestMessage(RequestMethod.ATTACH, session=session_id)
        self.id = message.id
        self._send(message, "attach")
        return session_id

    def detach(self, session_id: UUID) -> None:
        message = RequestMessage(RequestMethod.DETACH, session=session_id)
        self.id = message.id
        self._send(message, "detach")

    def begin(self, session_id: UUID | None = None) -> UUID:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.BEGIN, **kwargs)
        self.id = message.id
        response = self._send(message, "begin")
        self.check_response_for_result(response, "begin")
        result = response["result"]
        if isinstance(result, str):
            return UUID(result)
        if isinstance(result, list) and len(result) == 1:
            return UUID(str(result[0]))
        if isinstance(result, dict):
            txn_val = result.get("id") or result.get("txn")
            if txn_val is not None:
                return UUID(str(txn_val))
        raise ValueError(
            f"begin() expected transaction UUID from server, got: {type(result).__name__}"
        )

    def commit(self, txn_id: UUID, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"txn": txn_id}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.COMMIT, **kwargs)
        self.id = message.id
        self._send(message, "commit")

    def cancel(self, txn_id: UUID, session_id: UUID | None = None) -> None:
        if session_id is not None:
            message = RequestMessage(
                RequestMethod.CANCEL, txn=txn_id, session=session_id
            )
        else:
            message = RequestMessage(RequestMethod.CANCEL, txn=txn_id)
        self.id = message.id
        self._send(message, "cancel")

    def new_session(self) -> "BlockingSurrealSession":
        session_id = self.attach()
        return BlockingSurrealSession(self, session_id)

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()

    def __enter__(self) -> "BlockingWsSurrealConnection":
        """
        Synchronous context manager entry.
        Initializes a websocket connection and returns the connection instance.
        """
        self.socket = ws_sync.connect(
            self.raw_url, max_size=None, subprotocols=[websockets.Subprotocol("cbor")]
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Synchronous context manager exit.
        Closes the websocket connection upon exiting the context.
        """
        if self.socket is not None:
            self.socket.close()


class BlockingSurrealSession:
    def __init__(
        self,
        connection: BlockingWsSurrealConnection,
        session_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id

    def use(self, namespace: str, database: str) -> None:
        self._connection.use(namespace, database, session_id=self._session_id)

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> Value:
        return self._connection.query(query, vars, session_id=self._session_id)

    def signin(self, vars: dict[str, Value]) -> Tokens:
        return self._connection.signin(vars, session_id=self._session_id)

    def signup(self, vars: dict[str, Value]) -> Tokens:
        return self._connection.signup(vars, session_id=self._session_id)

    def authenticate(self, token: str) -> None:
        self._connection.authenticate(token, session_id=self._session_id)

    def invalidate(self) -> None:
        self._connection.invalidate(session_id=self._session_id)

    def let(self, key: str, value: Value) -> None:
        self._connection.let(key, value, session_id=self._session_id)

    def unset(self, key: str) -> None:
        self._connection.unset(key, session_id=self._session_id)

    def select(self, record: RecordIdType) -> Value:
        return self._connection.select(record, session_id=self._session_id)

    def create(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.create(record, data, session_id=self._session_id)

    def update(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.update(record, data, session_id=self._session_id)

    def merge(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.merge(record, data, session_id=self._session_id)

    def patch(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.patch(record, data, session_id=self._session_id)

    def delete(self, record: RecordIdType) -> Value:
        return self._connection.delete(record, session_id=self._session_id)

    def insert(
        self,
        table: str | Table,
        data: Value,
    ) -> Value:
        return self._connection.insert(table, data, session_id=self._session_id)

    def insert_relation(
        self,
        table: str | Table,
        data: Value,
    ) -> Value:
        return self._connection.insert_relation(
            table, data, session_id=self._session_id
        )

    def upsert(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.upsert(record, data, session_id=self._session_id)

    def live(
        self,
        table: str | Table,
        diff: bool = False,
    ) -> UUID:
        return self._connection.live(table, diff, session_id=self._session_id)

    def kill(self, query_uuid: str | UUID) -> None:
        self._connection.kill(query_uuid, session_id=self._session_id)

    def begin_transaction(self) -> "BlockingSurrealTransaction":
        txn_id = self._connection.begin(session_id=self._session_id)
        return BlockingSurrealTransaction(self._connection, self._session_id, txn_id)

    def close_session(self) -> None:
        self._connection.detach(self._session_id)


class BlockingSurrealTransaction:
    def __init__(
        self,
        connection: BlockingWsSurrealConnection,
        session_id: UUID,
        txn_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id
        self._txn_id = txn_id

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> Value:
        return self._connection.query(
            query,
            vars,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def select(self, record: RecordIdType) -> Value:
        return self._connection.select(
            record,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def create(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.create(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def update(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.update(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def merge(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.merge(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def patch(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.patch(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def delete(self, record: RecordIdType) -> Value:
        return self._connection.delete(
            record,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def insert(
        self,
        table: str | Table,
        data: Value,
    ) -> Value:
        return self._connection.insert(
            table,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def insert_relation(
        self,
        table: str | Table,
        data: Value,
    ) -> Value:
        return self._connection.insert_relation(
            table,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def upsert(
        self,
        record: RecordIdType,
        data: Value | None = None,
    ) -> Value:
        return self._connection.upsert(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def commit(self) -> None:
        self._connection.commit(self._txn_id, session_id=self._session_id)

    def cancel(self) -> None:
        self._connection.cancel(self._txn_id, session_id=self._session_id)
