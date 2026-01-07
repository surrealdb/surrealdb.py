import uuid
from types import TracebackType
from typing import Any, Optional, Union, cast

import requests

from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Value


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
        self.vars: dict[str, Value] = dict()
        self.session: Optional[requests.Session] = None

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
        self.token = token
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
        self.token = response["result"]
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

        # Check if we got an error
        if response.get("error"):
            error = response.get("error")
            # If INFO returns "No result found", try to get auth info via $auth
            # This happens when using record-level authentication
            if (
                error
                and error.get("code") == -32000
                and "No result found" in error.get("message", "")
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
            raise Exception(error)

        self.check_response_for_result(response, "getting database information")
        return response["result"]

    def use(self, namespace: str, database: str) -> None:
        message = RequestMessage(
            RequestMethod.USE,
            namespace=namespace,
            database=database,
        )
        self.id = message.id
        _ = self._send(message, "use")
        self.namespace = namespace
        self.database = database

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
        for key, value in self.vars.items():
            params[key] = value
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=params,
        )
        self.id = message.id
        response = self._send(message, "query", bypass=True)
        return response

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

    def let(self, key: str, value: Value) -> None:
        self.vars[key] = value

    def unset(self, key: str) -> None:
        self.vars.pop(key)

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

    def patch(self, record: RecordIdType, data: Optional[Value] = None) -> Value:
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

    def select(self, record: RecordIdType) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "select")
        return response["result"][0]["result"]

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

    def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        self.id = message.id
        response = self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

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

    def __enter__(self) -> "BlockingHttpSurrealConnection":
        """
        Synchronous context manager entry.
        Initializes a session for HTTP requests.
        """
        self.session = requests.Session()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """
        Synchronous context manager exit.
        Closes the HTTP session upon exiting the context.
        """
        if self.session is not None:
            self.session.close()
