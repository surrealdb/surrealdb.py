"""
A basic blocking connection to a SurrealDB instance.
"""

import uuid
from collections.abc import Generator
from typing import Any, Optional, Union
from uuid import UUID

import websockets
import websockets.sync.client as ws_sync

from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


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
        self.socket = None

    def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict:
        if self.socket is None:
            self.socket = ws_sync.connect(
                self.raw_url,
                max_size=None,
                subprotocols=[websockets.Subprotocol("cbor")],
            )
        self.socket.send(message.WS_CBOR_DESCRIPTOR)
        response = decode(self.socket.recv())
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

    def signup(self, vars: dict) -> str:
        message = RequestMessage(RequestMethod.SIGN_UP, data=vars)
        self.id = message.id
        response = self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        return response["result"]

    def signin(self, vars: dict[str, Any]) -> str:
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

    def info(self) -> dict:
        message = RequestMessage(RequestMethod.INFO)
        self.id = message.id
        response = self._send(message, "getting database information", bypass=True)

        # Check if we got an error
        if response.get("error"):
            error = response.get("error")
            # If INFO returns "No result found", try to get auth info via $auth
            # This happens when using record-level authentication
            if error.get("code") == -32000 and "No result found" in error.get(
                "message", ""
            ):
                # Try to get authenticated user record via $auth
                auth_response = self.query("SELECT * FROM $auth")
                if (
                    auth_response
                    and isinstance(auth_response, list)
                    and len(auth_response) > 0
                ):
                    return auth_response[0]
            # If it's a different error, raise it
            self.check_response_for_error(response, "getting database information")

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

    def query(self, query: str, vars: Optional[dict] = None) -> Union[list[dict], dict]:
        if vars is None:
            vars = {}
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=vars,
        )
        self.id = message.id
        response = self._send(message, "query")
        self.check_response_for_result(response, "query")
        return response["result"][0]["result"]

    def query_raw(self, query: str, params: Optional[dict] = None) -> dict:
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

    def let(self, key: str, value: Any) -> None:
        message = RequestMessage(RequestMethod.LET, key=key, value=value)
        self.id = message.id
        self._send(message, "letting")

    def unset(self, key: str) -> None:
        message = RequestMessage(RequestMethod.UNSET, params=[key])
        self.id = message.id
        self._send(message, "unsetting")

    def select(self, thing: Union[str, RecordID, Table]) -> Union[list[dict], dict]:
        variables = {}
        resource_ref = self._resource_to_variable(thing, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "select")
        return response["result"][0]["result"]

    def create(
        self,
        thing: Union[str, RecordID, Table],
        data: Optional[Union[Union[list[dict], dict], dict]] = None,
    ) -> Union[list[dict], dict]:
        variables = {}
        resource_ref = self._resource_to_variable(thing, variables, "_resource")

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

    def delete(self, thing: Union[str, RecordID, Table]) -> Union[list[dict], dict]:
        variables = {}
        resource_ref = self._resource_to_variable(thing, variables, "_resource")
        query = f"DELETE {resource_ref} RETURN BEFORE"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "delete")
        result = response["result"][0]["result"]
        # DELETE on a specific record returns a single dict, on a table returns a list
        return self._unwrap_result(
            result, unwrap=self._is_single_record_operation(thing)
        )

    def insert(
        self, table: Union[str, Table], data: Union[list[dict], dict]
    ) -> Union[list[dict], dict]:
        # Validate that table is not a RecordID
        if isinstance(table, RecordID):
            raise Exception(
                f"There was a problem with the database: Can not execute INSERT statement using value '{table}'"
            )

        variables = {}
        table_ref = self._resource_to_variable(table, variables, "_table")
        variables["_data"] = data
        query = f"INSERT INTO {table_ref} $_data"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "insert")
        return response["result"][0]["result"]

    def insert_relation(
        self, table: Union[str, Table], data: Union[list[dict], dict]
    ) -> Union[list[dict], dict]:
        variables = {}
        table_ref = self._resource_to_variable(table, variables, "_table")
        variables["_data"] = data
        query = f"INSERT RELATION INTO {table_ref} $_data"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "insert_relation")
        return response["result"][0]["result"]

    def merge(
        self, thing: Union[str, RecordID, Table], data: Optional[dict] = None
    ) -> Union[list[dict], dict]:
        variables = {}
        resource_ref = self._resource_to_variable(thing, variables, "_resource")

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
            result, unwrap=self._is_single_record_operation(thing)
        )

    def patch(
        self,
        thing: Union[str, RecordID, Table],
        data: Optional[list[dict]] = None,
    ) -> Union[list[dict], dict]:
        variables = {}
        resource_ref = self._resource_to_variable(thing, variables, "_resource")

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
            result, unwrap=self._is_single_record_operation(thing)
        )

    def subscribe_live(
        self,
        query_uuid: Union[str, UUID],
    ) -> Generator[dict, None, None]:
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
                    response = decode(self.socket.recv())

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
        self, thing: Union[str, RecordID, Table], data: Optional[dict] = None
    ) -> Union[list[dict], dict]:
        variables = {}
        resource_ref = self._resource_to_variable(thing, variables, "_resource")

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
            result, unwrap=self._is_single_record_operation(thing)
        )

    def upsert(
        self, thing: Union[str, RecordID, Table], data: Optional[dict] = None
    ) -> Union[list[dict], dict]:
        variables = {}
        resource_ref = self._resource_to_variable(thing, variables, "_resource")

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
            result, unwrap=self._is_single_record_operation(thing)
        )

    def close(self):
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

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        Synchronous context manager exit.
        Closes the websocket connection upon exiting the context.
        """
        if self.socket is not None:
            self.socket.close()
