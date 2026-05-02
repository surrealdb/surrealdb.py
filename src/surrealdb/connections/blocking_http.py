import uuid
from types import TracebackType
from typing import Any, cast, overload

import requests

from surrealdb.connections.builders import (
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
)
from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import UnsupportedFeatureError, parse_rpc_error
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Tokens, Value, parse_auth_result


class BlockingHttpSurrealConnection(SyncTemplate, UtilsMixin):
    def __init__(self, url: str) -> None:
        self.url: Url = Url(url)
        self.raw_url: str = url.rstrip("/")
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.token: str | None = None
        self.id: str = str(uuid.uuid4())
        self.namespace: str | None = None
        self.database: str | None = None
        self.vars: dict[str, Value] = dict()
        self.session: requests.Session | None = None

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

    def signup(self, vars: dict[str, Value]) -> Tokens:
        message = RequestMessage(RequestMethod.SIGN_UP, data=vars)
        self.id = message.id
        response = self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    def signin(self, vars: dict[str, Value]) -> Tokens:
        message = RequestMessage(RequestMethod.SIGN_IN, params=vars)
        self.id = message.id
        response = self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    def info(self) -> Value:
        message = RequestMessage(RequestMethod.INFO)
        self.id = message.id
        response = self._send(message, "getting database information", bypass=True)

        if response.get("error"):
            error = response.get("error")
            # If INFO returns "No result found", try to get auth info via $auth
            # This happens when using record-level authentication
            if (
                error
                and error.get("code") == -32000
                and "No result found" in error.get("message", "")
            ):
                auth_response = self.query("SELECT * FROM $auth")
                if (
                    auth_response
                    and isinstance(auth_response, list)
                    and len(auth_response) > 0
                ):
                    return auth_response[0]
            if error is not None:
                raise parse_rpc_error(error)

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

    def query(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> SyncQueryBuilder:
        return SyncQueryBuilder(
            executor=self._make_executor(),
            query=query,
            variables=vars,
        )

    def query_raw(
        self, query: str, params: dict[str, Value] | None = None
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

    def _make_executor(self) -> Any:
        def _executor(query: str, params: dict[str, Any]) -> dict[str, Any]:
            return self.query_raw(query, params)

        return _executor

    # CRUD overloads --------------------------------------------------------

    @overload
    def create(
        self, record: RecordID, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: Table, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: str, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self, record: RecordIdType, data: Value | None = None
    ) -> SyncCrudBuilder[Any]:
        return SyncCrudBuilder(
            executor=self._make_executor(),
            operation="CREATE",
            record=record,
            op_name="create",
            data=data,
            always_unwrap=True,
        )

    @overload
    def update(
        self, record: RecordID, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self, record: Table, data: Value | None = None
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(
        self, record: str, data: Value | None = None
    ) -> SyncCrudBuilder[Value]: ...
    def update(
        self, record: RecordIdType, data: Value | None = None
    ) -> SyncCrudBuilder[Any]:
        return SyncCrudBuilder(
            executor=self._make_executor(),
            operation="UPDATE",
            record=record,
            op_name="update",
            data=data,
        )

    @overload
    def upsert(
        self, record: RecordID, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self, record: Table, data: Value | None = None
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(
        self, record: str, data: Value | None = None
    ) -> SyncCrudBuilder[Value]: ...
    def upsert(
        self, record: RecordIdType, data: Value | None = None
    ) -> SyncCrudBuilder[Any]:
        return SyncCrudBuilder(
            executor=self._make_executor(),
            operation="UPSERT",
            record=record,
            op_name="upsert",
            data=data,
        )

    @overload
    def delete(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def delete(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> SyncCrudBuilder[Value]: ...
    def delete(self, record: RecordIdType) -> SyncCrudBuilder[Any]:
        return SyncCrudBuilder(
            executor=self._make_executor(),
            operation="DELETE",
            record=record,
            op_name="delete",
        )

    def insert(
        self,
        table: str | Table,
        data: Value | None = None,
        *,
        relation: bool = False,
    ) -> SyncInsertBuilder:
        return SyncInsertBuilder(
            executor=self._make_executor(),
            table=table,
            data=data,
            relation=relation,
        )

    def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        kwargs: dict[str, Any] = {"name": name}
        if version is not None:
            kwargs["version"] = version
        if args is not None:
            kwargs["args"] = args
        message = RequestMessage(RequestMethod.RUN, **kwargs)
        self.id = message.id
        response = self._send(message, "run")
        self.check_response_for_result(response, "run")
        return response["result"]

    def let(self, key: str, value: Value) -> None:
        self.vars[key] = value

    def unset(self, key: str) -> None:
        self.vars.pop(key)

    def select(self, record: RecordIdType) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "select")
        self._check_query_result(response["result"][0])
        return response["result"][0]["result"]

    def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        self.id = message.id
        response = self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    def __enter__(self) -> "BlockingHttpSurrealConnection":
        """
        Synchronous context manager entry.
        Initializes a session for HTTP requests.
        """
        self.session = requests.Session()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Synchronous context manager exit.
        Closes the HTTP session upon exiting the context.
        """
        if self.session is not None:
            self.session.close()

    def attach(self) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def detach(self, session_id: Any) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def begin(self, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def commit(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def cancel(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def new_session(self) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )
