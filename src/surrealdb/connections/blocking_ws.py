"""
A basic blocking connection to a SurrealDB instance.
"""

import threading
import uuid
from collections.abc import Generator
from types import TracebackType
from typing import Any, Optional, Union
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
from surrealdb.types import Value


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
        self.host: Optional[str] = self.url.hostname
        self.port: Optional[int] = self.url.port
        self.id: str = str(uuid.uuid4())
        self.token: Optional[str] = None
        self.socket: Optional[ClientConnection] = None
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

    def authenticate(self, token: str) -> None:
        message = RequestMessage(RequestMethod.AUTHENTICATE, token=token)
        self.id = message.id
        self._send(message, "authenticating")

    def invalidate(self) -> None:
        message = RequestMessage(RequestMethod.INVALIDATE)
        self.id = message.id
        self._send(message, "invalidating")
        self.token = None

    def signup(self, vars: dict[str, Value]) -> str:
        message = RequestMessage(RequestMethod.SIGN_UP, data=vars)
        self.id = message.id
        response = self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        return response["result"]

    def signin(self, vars: dict[str, Value]) -> str:
        message = RequestMessage(
            RequestMethod.SIGN_IN,
            username=vars.get("username"),
            password=vars.get("password"),
            access=vars.get("access"),
            database=vars.get("database"),
            namespace=vars.get("namespace"),
            variables=vars.get("variables"),
        )
        self.id = message.id
        response = self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        self.token = response["result"]
        return response["result"]

    def info(self) -> Value:
        message = RequestMessage(RequestMethod.INFO)
        self.id = message.id
        response = self._send(message, "getting database information", bypass=True)
        self.check_response_for_result(response, "getting database information")
        return response["result"]

    def use(self, namespace: str, database: str) -> None:
        message = RequestMessage(
            RequestMethod.USE,
            namespace=namespace,
            database=database,
        )
        self.id = message.id
        self._send(message, "use")

    def query(self, query: str, vars: Optional[dict[str, Value]] = None) -> Value:
        response = self.query_raw(query, vars)
        self.check_response_for_error(response, "query")
        self.check_response_for_result(response, "query")
        return response["result"][0]["result"]

    def query_raw(
        self, query: str, params: Optional[dict[str, Value]] = None
    ) -> dict[str, Any]:
        if params is None:
            params = {}
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=params,
        )
        self.id = message.id
        response = self._send(message, "query", bypass=True)
        return response

    def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        self.id = message.id
        response = self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    def let(self, key: str, value: Value) -> None:
        message = RequestMessage(RequestMethod.LET, key=key, value=value)
        self.id = message.id
        self._send(message, "letting")

    def unset(self, key: str) -> None:
        message = RequestMessage(RequestMethod.UNSET, params=[key])
        self.id = message.id
        self._send(message, "unsetting")

    def select(self, record: RecordIdType) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "select")
        return response["result"][0]["result"]

    def create(
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

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "create")
        result = response["result"][0]["result"]
        # CREATE always creates a single record, so always unwrap
        return self._unwrap_result(result, unwrap=True)

    def live(self, table: Union[str, Table], diff: bool = False) -> UUID:
        message = RequestMessage(
            RequestMethod.LIVE,
            table=table,
        )
        self.id = message.id
        response = self._send(message, "live")
        self.check_response_for_result(response, "live")
        return response["result"]

    def kill(self, query_uuid: Union[str, UUID]) -> None:
        message = RequestMessage(RequestMethod.KILL, uuid=query_uuid)
        self.id = message.id
        self._send(message, "kill")

    def delete(self, record: RecordIdType) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"DELETE {resource_ref} RETURN BEFORE"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "delete")
        result = response["result"][0]["result"]
        # DELETE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def insert(
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

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "insert")
        return response["result"][0]["result"]

    def insert_relation(
        self,
        table: Union[str, Table],
        data: Value,
    ) -> Value:
        variables: dict[str, Any] = {}
        table_ref = self._resource_to_variable(table, variables, "_table")
        variables["_data"] = data
        query = f"INSERT RELATION INTO {table_ref} $_data"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "insert_relation")
        return response["result"][0]["result"]

    def merge(self, record: RecordIdType, data: Optional[Value] = None) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref} MERGE {{}}"
        else:
            variables["_data"] = data
            query = f"UPDATE {resource_ref} MERGE $_data"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "merge")
        result = response["result"][0]["result"]
        # MERGE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def patch(
        self,
        record: RecordIdType,
        data: Optional[Value] = None,
    ) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref} PATCH []"
        else:
            variables["_patches"] = data
            query = f"UPDATE {resource_ref} PATCH $_patches"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "patch")
        result = response["result"][0]["result"]
        # PATCH on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def subscribe_live(
        self,
        query_uuid: Union[str, UUID],
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

    def update(self, record: RecordIdType, data: Optional[Value] = None) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPDATE {resource_ref}"
        else:
            variables["_content"] = data
            query = f"UPDATE {resource_ref} CONTENT $_content"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "update")
        result = response["result"][0]["result"]
        # UPDATE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

    def upsert(self, record: RecordIdType, data: Optional[Value] = None) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")

        if data is None:
            query = f"UPSERT {resource_ref}"
        else:
            variables["_content"] = data
            query = f"UPSERT {resource_ref} CONTENT $_content"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "upsert")
        result = response["result"][0]["result"]
        # UPSERT on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(record)
        )

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
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """
        Synchronous context manager exit.
        Closes the websocket connection upon exiting the context.
        """
        if self.socket is not None:
            self.socket.close()
