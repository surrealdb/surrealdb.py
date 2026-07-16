import uuid
from types import TracebackType
from typing import Any, cast, overload

import requests

from surrealdb.connections.builders import (
    _UNSET,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
)
from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import AUTH_FALLBACK_QUERY, UtilsMixin
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

        # Reuse the pooled session when running inside a context manager,
        # otherwise fall back to a fresh per-request request.
        if self.session is not None:
            response = self.session.post(url, headers=headers, data=data, timeout=30)
        else:
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

        if response.get("error") is not None:
            # Record-auth sessions have no ROOT/NS/DB info; re-resolve the
            # authenticated record via `$auth`.
            if self._info_needs_auth_fallback(response):
                record = self._extract_auth_record(
                    self.query(AUTH_FALLBACK_QUERY).first()
                )
                if record is not None:
                    return record
            raise parse_rpc_error(response["error"])

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
        """Run SurrealQL and return a builder; trigger it explicitly.

        ``.execute()`` returns ``list[Value]`` (one entry per statement, always
        a list - the v3 fix for issue #232), ``.first()`` returns the first
        statement's result (or ``None``), and ``.into(cls)`` maps the statement
        results onto a dataclass / class.
        """
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

    # CRUD (eager) ----------------------------------------------------------
    #
    # Passing ``data`` runs the operation immediately and returns the result;
    # the no-data form returns a builder so the caller can pick a clause.

    @overload
    def create(self, record: RecordIdType) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(self, record: RecordIdType, data: Value) -> dict[str, Value]: ...
    def create(
        self, record: RecordIdType, data: Value = _UNSET
    ) -> SyncCrudBuilder[dict[str, Value]] | dict[str, Value]:
        """Create a record (eager).

        ``db.create(record, data)`` runs ``CREATE ... CONTENT $data``
        immediately and returns the created record (``data=None`` runs
        ``CONTENT NULL``). ``db.create(record)`` (no data) returns a
        :class:`SyncCrudBuilder` so the caller can pick a terminal clause
        (``.content`` / ``.replace`` / ``.merge`` / ``.patch`` / ``.execute``).
        """
        builder: SyncCrudBuilder[dict[str, Value]] = SyncCrudBuilder(
            executor=self._make_executor(),
            operation="CREATE",
            record=record,
            op_name="create",
            always_unwrap=True,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def update(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def update(self, record: RecordID, data: Value) -> dict[str, Value]: ...
    @overload
    def update(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def update(self, record: str, data: Value) -> Value: ...
    def update(
        self, record: RecordIdType, data: Value = _UNSET
    ) -> SyncCrudBuilder[Any] | Value:
        """Update records, replacing existing content by default (eager).

        ``db.update(record, data)`` runs eagerly and returns the result
        (``data=None`` runs ``CONTENT NULL``); the no-data form returns a
        :class:`SyncCrudBuilder` with terminal clause methods.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(),
            operation="UPDATE",
            record=record,
            op_name="update",
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def upsert(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def upsert(self, record: RecordID, data: Value) -> dict[str, Value]: ...
    @overload
    def upsert(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def upsert(self, record: str, data: Value) -> Value: ...
    def upsert(
        self, record: RecordIdType, data: Value = _UNSET
    ) -> SyncCrudBuilder[Any] | Value:
        """Insert or update records (eager).

        ``db.upsert(record, data)`` runs eagerly and returns the result
        (``data=None`` runs ``CONTENT NULL``); the no-data form returns a
        :class:`SyncCrudBuilder` with terminal clause methods.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(),
            operation="UPSERT",
            record=record,
            op_name="upsert",
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def delete(self, record: RecordID) -> dict[str, Value]: ...
    @overload
    def delete(self, record: Table) -> list[Value]: ...
    @overload
    def delete(self, record: str) -> Value: ...
    def delete(self, record: RecordIdType) -> Value:
        """Delete records eagerly and return the deleted record(s).

        A ``RecordID`` (or ``"table:id"``) returns the single deleted record; a
        ``Table`` (or bare name) returns the list of deleted records.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(),
            operation="DELETE",
            record=record,
            op_name="delete",
        )
        return cast(Value, builder.execute())

    @overload
    def insert(
        self, table: str | Table, *, relation: bool = False
    ) -> SyncInsertBuilder: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, relation: bool = False
    ) -> list[Value]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        relation: bool = False,
    ) -> SyncInsertBuilder | list[Value]:
        """Insert record(s) or relation(s) into a table (eager).

        ``db.insert(table, data)`` runs immediately and returns the inserted
        records. ``db.insert(table)`` (no data) returns a
        :class:`SyncInsertBuilder`; pass ``relation=True`` (or chain
        ``.relation()``) for ``INSERT RELATION INTO`` and run it with
        ``.content(data)`` / ``.execute()``.
        """
        builder = SyncInsertBuilder(
            executor=self._make_executor(),
            table=table,
            relation=relation,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

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

    @overload
    def select(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def select(self, record: Table) -> list[Value]: ...
    @overload
    def select(self, record: str) -> Value: ...
    def select(self, record: RecordIdType) -> Value:
        """Select records eagerly.

        A ``RecordID`` (or ``"table:id"``) returns the record dict, or ``None``
        when it is absent. A ``Table`` (or bare table-name string) returns the
        list of records.
        """
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = self.query_raw(query, variables)
        self.check_response_for_error(response, "select")
        self._check_query_result(response["result"][0])
        result = response["result"][0]["result"]
        # Single-record targets (RecordID / "table:id") unwrap the one-element
        # result list to the record dict, or None when the record is absent.
        if self._is_single_record_operation(record):
            if isinstance(result, list):
                return result[0] if result else None
            return result
        return result

    def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        self.id = message.id
        response = self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    def close(self) -> None:
        """Close the pooled HTTP session if one is open.

        Idempotent: a no-op when no session has been opened (for example
        outside a ``with`` block) and safe to call more than once.
        """
        if self.session is not None:
            self.session.close()
        self.session = None

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
        self.close()

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
