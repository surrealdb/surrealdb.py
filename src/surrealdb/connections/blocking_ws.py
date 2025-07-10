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
        message = RequestMessage(RequestMethod.AUTHENTICATE, [token])
        self._send(message, "authenticating")

    def invalidate(self) -> None:
        message = RequestMessage(RequestMethod.INVALIDATE)
        self._send(message, "invalidating")
        self.token = None

    def signup(self, vars: dict) -> str:
        message = RequestMessage(RequestMethod.SIGN_UP, [vars])
        response = self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        return response["result"]

    def signin(self, vars: dict[str, Any]) -> str:
        message = RequestMessage(RequestMethod.SIGN_IN, [vars])
        response = self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        self.token = response["result"]
        return response["result"]

    def info(self) -> dict:
        message = RequestMessage(RequestMethod.INFO)
        outcome = self._send(message, "getting database information")
        self.check_response_for_result(outcome, "getting database information")
        return outcome["result"]

    def use(self, namespace: str, database: str) -> None:
        message = RequestMessage(RequestMethod.USE, [namespace, database])
        self._send(message, "use")

    def query(self, query: str, vars: Optional[dict] = None) -> Union[list[dict], dict]:
        if vars is None:
            vars = {}
        message = RequestMessage(RequestMethod.QUERY, [query, vars])
        response = self._send(message, "query")
        self.check_response_for_result(response, "query")
        return response["result"][0]["result"]

    def query_raw(self, query: str, params: Optional[dict] = None) -> dict:
        if params is None:
            params = {}
        message = RequestMessage(RequestMethod.QUERY, [query, params])
        response = self._send(message, "query", bypass=True)
        return response

    def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        response = self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    def let(self, key: str, value: Any) -> None:
        message = RequestMessage(RequestMethod.LET, [key, value])
        self._send(message, "letting")

    def unset(self, key: str) -> None:
        message = RequestMessage(RequestMethod.UNSET, [key])
        self._send(message, "unsetting")

    def select(self, thing: Union[str, RecordID, Table]) -> Union[list[dict], dict]:
        message = RequestMessage(RequestMethod.SELECT, [thing])
        response = self._send(message, "select")
        self.check_response_for_result(response, "select")
        return response["result"]

    def create(
        self,
        thing: Union[str, RecordID, Table],
        data: Optional[Union[Union[list[dict], dict], dict]] = None,
    ) -> Union[list[dict], dict]:
        if isinstance(thing, str):
            if ":" in thing:
                buffer = thing.split(":")
                thing = RecordID(table_name=buffer[0], identifier=buffer[1])
            else:
                thing = Table(table_name=thing)

        if data is None:
            message = RequestMessage(RequestMethod.CREATE, [thing])
        else:
            message = RequestMessage(RequestMethod.CREATE, [thing, data])
        response = self._send(message, "create")
        self.check_response_for_result(response, "create")
        return response["result"]

    def live(self, table: Union[str, Table], diff: bool = False) -> UUID:
        if isinstance(table, str):
            table = Table(table_name=table)

        message = RequestMessage(RequestMethod.LIVE, [table])
        response = self._send(message, "live")
        self.check_response_for_result(response, "live")
        return UUID(response["result"])

    def kill(self, query_uuid: Union[str, UUID]) -> None:
        message = RequestMessage(RequestMethod.KILL, [str(query_uuid)])
        self._send(message, "kill")

    def delete(self, thing: Union[str, RecordID, Table]) -> Union[list[dict], dict]:
        if isinstance(thing, str):
            if ":" in thing:
                buffer = thing.split(":")
                thing = RecordID(table_name=buffer[0], identifier=buffer[1])
            else:
                thing = Table(table_name=thing)

        message = RequestMessage(RequestMethod.DELETE, [thing])
        response = self._send(message, "delete")
        self.check_response_for_result(response, "delete")
        return response["result"]

    def insert(
        self, table: Union[str, Table], data: Union[list[dict], dict]
    ) -> Union[list[dict], dict]:
        if isinstance(table, str):
            table = Table(table_name=table)

        message = RequestMessage(RequestMethod.INSERT, [table, data])
        response = self._send(message, "insert")
        self.check_response_for_result(response, "insert")
        return response["result"]

    def insert_relation(
        self, table: Union[str, Table], data: Union[list[dict], dict]
    ) -> Union[list[dict], dict]:
        if isinstance(table, str):
            table = Table(table_name=table)

        message = RequestMessage(RequestMethod.INSERT_RELATION, [table, data])
        response = self._send(message, "insert_relation")
        self.check_response_for_result(response, "insert_relation")
        return response["result"]

    def merge(
        self, thing: Union[str, RecordID, Table], data: Optional[dict] = None
    ) -> Union[list[dict], dict]:
        if isinstance(thing, str):
            if ":" in thing:
                buffer = thing.split(":")
                thing = RecordID(table_name=buffer[0], identifier=buffer[1])
            else:
                thing = Table(table_name=thing)

        if data is None:
            message = RequestMessage(RequestMethod.MERGE, [thing])
        else:
            message = RequestMessage(RequestMethod.MERGE, [thing, data])
        response = self._send(message, "merge")
        self.check_response_for_result(response, "merge")
        return response["result"]

    def patch(
        self, thing: Union[str, RecordID, Table], data: Optional[list[dict]] = None
    ) -> Union[list[dict], dict]:
        if isinstance(thing, str):
            if ":" in thing:
                buffer = thing.split(":")
                thing = RecordID(table_name=buffer[0], identifier=buffer[1])
            else:
                thing = Table(table_name=thing)

        message = RequestMessage(RequestMethod.PATCH, [thing, data])
        response = self._send(message, "patch")
        self.check_response_for_result(response, "patch")
        return response["result"]

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
        if isinstance(thing, str):
            if ":" in thing:
                buffer = thing.split(":")
                thing = RecordID(table_name=buffer[0], identifier=buffer[1])
            else:
                thing = Table(table_name=thing)

        if data is None:
            message = RequestMessage(RequestMethod.UPDATE, [thing])
        else:
            message = RequestMessage(RequestMethod.UPDATE, [thing, data])
        response = self._send(message, "update")
        self.check_response_for_result(response, "update")
        return response["result"]

    def upsert(
        self, thing: Union[str, RecordID, Table], data: Optional[dict] = None
    ) -> Union[list[dict], dict]:
        if isinstance(thing, str):
            if ":" in thing:
                buffer = thing.split(":")
                thing = RecordID(table_name=buffer[0], identifier=buffer[1])
            else:
                thing = Table(table_name=thing)

        if data is None:
            message = RequestMessage(RequestMethod.UPSERT, [thing])
        else:
            message = RequestMessage(RequestMethod.UPSERT, [thing, data])
        response = self._send(message, "upsert")
        self.check_response_for_result(response, "upsert")
        return response["result"]

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
