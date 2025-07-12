import uuid
from typing import Any, Optional, Union, cast

import requests

from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


class BlockingHttpSurrealConnection(SyncTemplate, UtilsMixin):
    def __init__(self, url: str) -> None:
        self.url: Url = Url(url)
        self.raw_url: str = url.rstrip("/")
        self.host: Optional[str] = self.url.hostname
        self.port: Optional[int] = self.url.port
        self.token: Optional[str] = None
        self.id: str = str(uuid.uuid4())
        self.namespace: Optional[str] = None
        self.database: Optional[str] = None
        self.vars: dict[str, Any] = dict()

    def _send(
        self, message: RequestMessage, operation: str, bypass: bool = False
    ) -> dict[str, Any]:
        data = message.WS_CBOR_DESCRIPTOR
        url = f"{self.url.raw_url}/rpc"
        headers = {
            "Accept": "application/cbor",
            "Content-Type": "application/cbor",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.namespace:
            headers["Surreal-NS"] = self.namespace
        if self.database:
            headers["Surreal-DB"] = self.database

        response = requests.post(url, headers=headers, data=data, timeout=30)
        response.raise_for_status()

        raw_cbor = response.content
        data_dict = cast(dict[str, Any], decode(raw_cbor))

        if not bypass:
            self.check_response_for_error(data_dict, operation)

        return data_dict

    def set_token(self, token: str) -> None:
        self.token = token

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
        self.namespace = namespace
        self.database = database

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

    def let(self, key: str, value: Any) -> None:
        message = RequestMessage(RequestMethod.LET, [key, value])
        self._send(message, "letting")

    def unset(self, key: str) -> None:
        message = RequestMessage(RequestMethod.UNSET, [key])
        self._send(message, "unsetting")

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

    def select(self, thing: Union[str, RecordID, Table]) -> Union[list[dict], dict]:
        message = RequestMessage(RequestMethod.SELECT, [thing])
        response = self._send(message, "select")
        self.check_response_for_result(response, "select")
        return response["result"]

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

    def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        response = self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
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

    def close(self) -> None:
        """
        Blocking HTTP connections don't need to be closed as they create new sessions for each request.
        This method is provided for compatibility with the test framework.
        """
        pass

    def __enter__(self) -> "BlockingHttpSurrealConnection":
        """
        Synchronous context manager entry.
        Initializes a session for HTTP requests.
        """
        self.session = requests.Session()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        Synchronous context manager exit.
        Closes the HTTP session upon exiting the context.
        """
        if hasattr(self, "session"):
            self.session.close()
