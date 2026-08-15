import asyncio
import uuid
from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any, cast, overload
from uuid import UUID

import aiohttp

from surrealdb.connections.async_template import AsyncTemplate
from surrealdb.connections.builders import (
    _UNSET,
    AsyncCrudBuilder,
    AsyncInsertBuilder,
    AsyncQueryBuilder,
    M,
    _map_result,
)
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import (
    AUTH_FALLBACK_QUERY,
    UtilsMixin,
    build_run_query,
    merge_query_vars,
)
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ConnectionUnavailableError,
    TransportTimeoutError,
    UnsupportedFeatureError,
    parse_rpc_error,
)
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Tokens, Value, parse_auth_result

# Live queries need a persistent connection to push notifications down, which
# is what makes them a websocket-only feature - as the README documents.
_NO_LIVE_QUERIES = (
    "Live queries are only supported for WebSocket connections; HTTP has no "
    "persistent connection for notifications to arrive on"
)


class AsyncHttpSurrealConnection(AsyncTemplate, UtilsMixin):
    """
    An async connection to a SurrealDB instance using HTTP.

    # Notes
    When used as an async context manager (``async with``) a single pooled
    ``aiohttp.ClientSession`` is created and reused across every request, then
    closed on exit. Outside a context manager a fresh session is created per
    request.

    Attributes:
        url: The URL of the database to process queries for.
        id: The ID of the connection.
    """

    def __init__(
        self,
        url: str,
    ) -> None:
        """
        Constructor for the AsyncHttpSurrealConnection class.

        :param url: (str) The URL of the database to process queries for.
        """
        self.url: Url = Url(url)
        self.raw_url: str = self.url.raw_url
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.token: str | None = None
        self.id: str = str(uuid.uuid4())
        self.namespace: str | None = None
        self.database: str | None = None
        self.vars: dict[str, Value] = {}
        self._session: aiohttp.ClientSession | None = None

    async def _send(
        self,
        message: RequestMessage,
        operation: str,
        bypass: bool = False,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Send one RPC over HTTP.

        *token* authorises this request alone, without adopting it as the
        connection's identity - see :meth:`authenticate`.
        """
        data = message.WS_CBOR_DESCRIPTOR
        url = f"{self.url.raw_url}/rpc"
        headers: dict[str, str] = {}
        headers["Accept"] = "application/cbor"
        headers["content-type"] = "application/cbor"
        bearer = self.token if token is None else token
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        if self.namespace:
            headers["Surreal-NS"] = self.namespace
        if self.database:
            headers["Surreal-DB"] = self.database

        # Reuse the pooled session when running inside a context manager,
        # otherwise fall back to a fresh per-request session.
        if self._session is not None and not self._session.closed:
            return await self._request(
                self._session, url, headers, data, operation, bypass
            )
        async with aiohttp.ClientSession() as session:
            return await self._request(session, url, headers, data, operation, bypass)

    async def _request(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: dict[str, str],
        data: bytes,
        operation: str,
        bypass: bool,
    ) -> dict[str, Any]:
        try:
            async with session.request(
                method="POST",
                url=url,
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                status = response.status
                raw_cbor = await response.read()
        except asyncio.TimeoutError as exc:
            raise TransportTimeoutError(
                f"timed out while {operation} against {url}: {exc}"
            ) from exc
        except aiohttp.ClientError as exc:
            raise ConnectionUnavailableError(
                f"could not reach {url} while {operation}: {exc}"
            ) from exc

        self.check_status_for_error(status, raw_cbor, url)

        result = self.decode_response(raw_cbor, operation)
        if bypass is False:
            self.check_response_for_error(result, operation)
        return result

    async def authenticate(self, token: str) -> None:
        """Authenticate this connection with an existing token.

        The token authorises the ``authenticate`` request itself and is only
        adopted as the connection's identity once the server accepts it.
        Assigning it up front attached a rejected token to every later request
        - including the ``signin`` that would have recovered the connection,
        which the server then answered ``401`` - so one failed ``authenticate``
        left the connection permanently unusable, with no way back short of
        building a new one.
        """
        message = RequestMessage(RequestMethod.AUTHENTICATE, token=token)
        self.id = message.id
        await self._send(message, "authenticating", token=token)
        self.token = token

    async def invalidate(self) -> None:
        message = RequestMessage(RequestMethod.INVALIDATE)
        self.id = message.id
        await self._send(message, "invalidating")
        self.token = None

    async def signup(self, vars: dict[str, Value]) -> Tokens:
        message = RequestMessage(RequestMethod.SIGN_UP, data=vars)
        self.id = message.id
        response = await self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    async def signin(self, vars: dict[str, Value]) -> Tokens:
        message = RequestMessage(RequestMethod.SIGN_IN, params=vars)
        self.id = message.id
        response = await self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    async def info(self) -> Value:
        message = RequestMessage(RequestMethod.INFO)
        self.id = message.id
        response = await self._send(
            message, "getting database information", bypass=True
        )

        if response.get("error") is not None:
            # Record-auth sessions have no ROOT/NS/DB info; re-resolve the
            # authenticated record via `$auth`.
            if self._info_needs_auth_fallback(response):
                record = self._extract_auth_record(
                    await self.query(AUTH_FALLBACK_QUERY).first()
                )
                if record is not None:
                    return record
            raise parse_rpc_error(response["error"])

        self.check_response_for_result(response, "getting database information")
        return cast(dict[str, Value], response["result"])

    async def use(self, namespace: str, database: str) -> None:
        message = RequestMessage(
            RequestMethod.USE,
            namespace=namespace,
            database=database,
        )
        self.id = message.id
        _ = await self._send(message, "use")
        self.namespace = namespace
        self.database = database

    def query(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> AsyncQueryBuilder:
        """Run SurrealQL and return an awaitable builder.

        Awaiting it (or ``.execute()``) returns ``list[Value]`` - one entry per
        statement, always a list (the v3 fix for issue #232). Use ``.first()``
        for the first statement's result, or ``.into(cls)`` to map the results
        onto a dataclass / class.
        """
        return AsyncQueryBuilder(
            executor=self._make_executor(),
            query=query,
            variables=vars,
        )

    async def query_raw(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> dict[str, Any]:
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=merge_query_vars(self.vars, vars),
        )
        self.id = message.id
        response = await self._send(message, "query", bypass=True)
        return response

    def _make_executor(self) -> Any:
        async def _executor(query: str, params: dict[str, Any]) -> dict[str, Any]:
            return await self.query_raw(query, params)

        return _executor

    # CRUD overloads --------------------------------------------------------

    @overload
    def create(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def create(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: str, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Create a record; returns an awaitable builder.

        ``await db.create(record, data)`` is sugar for
        ``await db.create(record).content(data)``. Clause methods
        (``.content`` / ``.replace`` / ``.merge`` / ``.patch``) return the
        builder so it stays awaitable. Pass ``into=Model`` to map the created
        record onto ``Model``.
        """
        builder: AsyncCrudBuilder[Any] = AsyncCrudBuilder(
            executor=self._make_executor(),
            operation="CREATE",
            record=record,
            op_name="create",
            always_unwrap=True,
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def update(
        self, record: RecordID, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def update(
        self, record: Table, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def update(
        self, record: str, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str, data: Value = _UNSET) -> AsyncCrudBuilder[Value]: ...
    def update(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Update records; returns an awaitable builder.

        Optional clause methods ``.content`` / ``.replace`` / ``.merge`` /
        ``.patch`` return the builder so it stays awaitable. Pass ``into=Model``
        to map the returned record(s) onto ``Model`` / ``list[Model]``.
        """
        builder: AsyncCrudBuilder[Any] = AsyncCrudBuilder(
            executor=self._make_executor(),
            operation="UPDATE",
            record=record,
            op_name="update",
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def upsert(
        self, record: RecordID, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def upsert(
        self, record: Table, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(
        self, record: str, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str, data: Value = _UNSET) -> AsyncCrudBuilder[Value]: ...
    def upsert(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Insert or update records; returns an awaitable builder.

        Optional clause methods ``.content`` / ``.replace`` / ``.merge`` /
        ``.patch`` return the builder so it stays awaitable. Pass ``into=Model``
        to map the returned record(s) onto ``Model`` / ``list[Model]``.
        """
        builder: AsyncCrudBuilder[Any] = AsyncCrudBuilder(
            executor=self._make_executor(),
            operation="UPSERT",
            record=record,
            op_name="upsert",
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def delete(
        self, record: RecordID, *, into: type[M]
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self, record: str, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(self, record: RecordID) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(self, record: Table) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> AsyncCrudBuilder[Value]: ...
    def delete(
        self, record: RecordIdType, *, into: type[M] | None = None
    ) -> AsyncCrudBuilder[Any]:
        """Delete records; returns an awaitable builder.

        A ``RecordID`` (or ``"table:id"``) resolves to the deleted record, or
        ``None`` when no record was deleted (matching select); a ``Table`` (or
        bare name) to the list of deleted records. ``DELETE`` has no clause
        methods. Pass ``into=Model`` to map the deleted record(s) onto ``Model``.
        """
        return AsyncCrudBuilder(
            executor=self._make_executor(),
            operation="DELETE",
            record=record,
            op_name="delete",
            into=into,
        )

    @overload
    def insert(
        self, table: str | Table, data: Value = _UNSET, *, relation: bool = False
    ) -> AsyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M],
        relation: bool = False,
    ) -> AsyncInsertBuilder[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
    ) -> AsyncInsertBuilder[Any]:
        """Insert record(s) or relation(s); returns an awaitable builder.

        Pass ``relation=True`` (or chain ``.relation()``) for ``INSERT
        RELATION INTO``. Awaiting the builder (or ``.execute()``) runs it. Pass
        ``into=Model`` to map the inserted records onto ``list[Model]``.
        """
        builder: AsyncInsertBuilder[Any] = AsyncInsertBuilder(
            executor=self._make_executor(),
            table=table,
            relation=relation,
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    async def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        """Call a SurrealDB function and return its result.

        When variables are bound with :meth:`let`, this is sent as a query
        rather than as the ``run`` RPC. HTTP has no server-side session, so the
        RPC - which carries no parameters - left a function reading a
        ``let()``-bound variable seeing nothing, and the call quietly returned
        ``None`` where the websocket transports returned the value. Query
        parameters do reach a function body, so replaying the bindings that way
        makes the two agree.

        :raises UnsupportedFeatureError: if *version* is given while session
            variables are bound. SurrealQL has no syntax for calling a specific
            function version, so the two cannot be combined over HTTP.
        """
        if self.vars:
            if version is not None:
                raise UnsupportedFeatureError(
                    "run() cannot combine a function version with let() "
                    "variables over HTTP: the version needs the `run` RPC, "
                    "which carries no parameters, and the variables need a "
                    "query, which has no syntax for a version. Use a websocket "
                    "connection, pass the values as arguments, or unset() the "
                    "session variables first."
                )
            query, arguments = build_run_query(name, args)
            return await self.query(query, arguments).first()

        kwargs: dict[str, Any] = {"name": name}
        if version is not None:
            kwargs["version"] = version
        if args is not None:
            kwargs["args"] = args
        message = RequestMessage(RequestMethod.RUN, **kwargs)
        self.id = message.id
        response = await self._send(message, "run")
        self.check_response_for_result(response, "run")
        return response["result"]

    async def let(self, key: str, value: Value) -> None:
        self.vars[key] = value

    async def unset(self, key: str) -> None:
        # Unsetting a name that was never set is not an error: the websocket
        # and embedded engines answer the `unset` RPC for an unknown key
        # without complaint, and only here did it raise `KeyError` - an
        # exception outside the `SurrealError` tree, so `except SurrealError`
        # around transport-agnostic cleanup code did not catch it.
        self.vars.pop(key, None)

    @overload
    async def select(self, record: RecordID, *, into: type[M]) -> M | None: ...
    @overload
    async def select(self, record: Table, *, into: type[M]) -> list[M]: ...
    @overload
    async def select(self, record: str, *, into: type[M]) -> M | list[M] | None: ...
    @overload
    async def select(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    async def select(self, record: Table) -> list[Value]: ...
    @overload
    async def select(self, record: str) -> Value: ...
    async def select(self, record: RecordIdType, *, into: type[M] | None = None) -> Any:
        """Select records.

        A ``RecordID`` (or ``"table:id"``) returns the record dict, or ``None``
        when it is absent. A ``Table`` (or bare table-name string) returns the
        list of records. Pass ``into=Model`` to map each record onto ``Model``.
        """
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "select")
        self._check_query_result(response["result"][0])
        result = response["result"][0]["result"]
        # Single-record targets (RecordID / "table:id") unwrap the one-element
        # result list to the record dict, or None when the record is absent.
        if self._is_single_record_operation(record):
            if isinstance(result, list):
                value: Any = result[0] if result else None
            else:
                value = result
        else:
            value = result
        if into is not None:
            return _map_result(into, value)
        return value

    async def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        self.id = message.id
        response = await self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    async def connect(self, url: str | None = None) -> None:
        """Accept the connect step; HTTP opens no persistent connection.

        Requests are sent per call, so there is nothing to establish up front.
        This exists so code written against the connection API works on every
        transport - previously the inherited default raised
        ``NotImplementedError`` here while the websocket transports connected,
        so transport-agnostic code broke on HTTP alone.

        Passing *url* re-points the connection, matching the websocket
        transports.
        """
        if url is not None:
            self.url = Url(url)
            self.raw_url = self.url.raw_url
            self.host = self.url.hostname
            self.port = self.url.port

    async def close(self) -> None:
        """Close the pooled HTTP session if one is open.

        Idempotent: a no-op when no session has been opened (for example
        outside an ``async with`` block) and safe to call more than once.
        """
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def __aenter__(self) -> "AsyncHttpSurrealConnection":
        """Open the pooled HTTP session if there isn't one, and return ``self``.

        Reuses an existing open session rather than assigning a fresh one. The
        replaced ``ClientSession`` was never closed, so it leaked its connector
        and sockets and emitted aiohttp's "Unclosed client session" warning -
        and ``__aexit__`` closed only the replacement. This mirrors the
        websocket transport, where re-entering also cost the server-side
        session.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Asynchronous context manager exit.
        Closes the aiohttp session upon exiting the context.
        """
        await self.close()

    # Live queries -----------------------------------------------------------
    #
    # Refused the same way the session and transaction methods below are.
    # Inherited, they raised ``NotImplementedError`` from the template - which
    # is not a ``SurrealError``, so ``except SurrealError`` missed it even
    # though ``attach()`` beside it was covered.

    async def live(self, table: str | Table, diff: bool = False) -> UUID:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    async def kill(self, query_uuid: str | UUID) -> None:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    async def subscribe_live(
        self, query_uuid: str | UUID
    ) -> AsyncGenerator[dict[str, Value], None]:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    async def attach(self) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def detach(self, session_id: Any) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def begin(self, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def commit(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def cancel(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def new_session(self) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )
