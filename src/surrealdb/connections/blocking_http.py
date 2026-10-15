import inspect
import threading
import time
import uuid
from collections.abc import Generator, Mapping, Sequence
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, overload
from uuid import UUID

import requests

from surrealdb.connections.api import (
    ApiResponse,
    build_api_query,
    graphql_params,
    statement_results,
)
from surrealdb.connections.auth_provider import (
    AuthCredentials,
    AuthProvider,
    check_auth_provider,
    check_credentials,
    renewal_due,
)
from surrealdb.connections.batch import Batch
from surrealdb.connections.builders import (
    _UNSET,
    M,
    RelateEdge,
    RelateEnd,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
    _Executor,
    relate_builder,
)
from surrealdb.connections.files import BlockingFiles
from surrealdb.connections.health import check_health
from surrealdb.connections.http_body import read_body
from surrealdb.connections.import_export import (
    ExportOptions,
    ExportTarget,
    ImportData,
    export_sql,
    export_sql_to,
    import_sql,
)
from surrealdb.connections.server_version import ServerVersionMixin
from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.timeouts import (
    DEFAULT_TIMEOUT,
    check_timeout,
    describe,
    effective_timeout,
    scoped_timeout,
)
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import (
    AUTH_FALLBACK_QUERY,
    UtilsMixin,
    build_run_query,
    merge_query_vars,
)
from surrealdb.data.types.null import NullType
from surrealdb.data.types.record_id import RecordID, RecordIdType, StringRecordId
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ConnectionUnavailableError,
    ServerError,
    TransportTimeoutError,
    UnsupportedFeatureError,
    parse_rpc_error,
)
from surrealdb.features import Features
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.streaming import (
    UNSUPPORTED_BY_HTTP,
    QueryStream,
    SyncStreamOps,
    buffered_statements,
)
from surrealdb.types import Tokens, Value, parse_auth_result

# Live queries need a persistent connection to push notifications down, which
# is what makes them a websocket-only feature - as the README documents.
_NO_LIVE_QUERIES = (
    "Live queries are only supported for WebSocket connections; HTTP has no "
    "persistent connection for notifications to arrive on"
)


class BlockingHttpSurrealConnection(SyncTemplate, UtilsMixin, ServerVersionMixin):
    def __init__(
        self,
        url: str,
        *,
        timeout: float | None = DEFAULT_TIMEOUT,
        version_check: bool = True,
        auth: AuthProvider | None = None,
        renew_access: bool = True,
    ) -> None:
        """
        :param url: The URL of the database to process queries for.
        :param timeout: Seconds to wait for each request to complete, or
            ``None`` to wait indefinitely. Defaults to 30. Override it for a
            block of requests with :meth:`timeout`.
        :param version_check: Refuse to talk to a server outside the versions
            this SDK supports - see :mod:`surrealdb.features`. On by default.
            The version is asked for once, before the first request.
        :param auth: How the connection signs itself in before its first
            request: signin credentials, an access token, :class:`Tokens`, or
            a function returning one of those - see
            :mod:`surrealdb.connections.auth_provider`.
        :param renew_access: Renew the access token shortly before it
            expires, with the refresh token or else with *auth*, before the
            request that finds it due. On by default.
        """
        check_auth_provider(auth)
        self.url: Url = Url(url)
        self._version_check = version_check
        self._auth_provider: AuthProvider | None = auth
        self._renew_access = renew_access
        self._authorising = False
        self._auth_lock = threading.RLock()
        # Whether this connection's identity has been chosen - by ``auth=`` or
        # by the caller signing in or out - so that ``auth=`` is applied once,
        # not again after an explicit sign-out.
        self._auth_settled = False
        self._timeout: float | None = check_timeout("timeout", timeout)
        self.raw_url: str = url.rstrip("/")
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.token: str | None = None
        self._refresh_token: str | None = None
        self.id: str = str(uuid.uuid4())
        self.namespace: str | None = None
        self.database: str | None = None
        self.vars: dict[str, Value] = {}
        self.session: requests.Session | None = None

    def timeout(self, seconds: float | None) -> AbstractContextManager[None]:
        """Wait *seconds* for each reply to a request made inside the block.

        Overrides the connection's ``timeout`` for the code inside the ``with``
        block only, so a slow import or a long report can wait longer without
        changing the default for everything else on the connection. ``None``
        waits indefinitely::

            with db.timeout(300):
                db.query("SELECT * FROM big_table")
        """
        return scoped_timeout(self, seconds)

    def _handshake(self) -> None:
        """Ask the server for its version, once, before the first request."""
        try:
            response = self._send(
                RequestMessage(RequestMethod.VERSION),
                "checking the server version",
                token="",
            )
        except ServerError:
            self._adopt_server_version(None)
            return
        self._adopt_server_version(response.get("result"))

    def _send(
        self,
        message: RequestMessage,
        operation: str,
        bypass: bool = False,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Send one RPC over HTTP.

        *token* authorises this request alone, without adopting it as the
        connection's identity - see :meth:`authenticate`. An empty *token*
        sends the request anonymously.
        """
        if message.method is not RequestMethod.VERSION:
            self._authorise()
        if not self._version_learned and message.method is not RequestMethod.VERSION:
            self._handshake()
        data = message.WS_CBOR_DESCRIPTOR
        url = f"{self.url.raw_url}/rpc"
        headers = {
            "Accept": "application/cbor",
            "Content-Type": "application/cbor",
        }
        bearer = self.token if token is None else token
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        if self.namespace:
            headers["Surreal-NS"] = self.namespace
        if self.database:
            headers["Surreal-DB"] = self.database

        # Reuse the pooled session when running inside a context manager,
        # otherwise fall back to a fresh per-request request.
        timeout = effective_timeout(self, self._timeout)
        # requests' own timeout bounds each wait for the socket, not the
        # whole exchange, so a reply trickling in could run on without end.
        # The body is read here against the deadline instead.
        deadline = None if timeout is None else time.monotonic() + timeout
        try:
            if self.session is not None:
                response = self.session.post(
                    url, headers=headers, data=data, timeout=timeout, stream=True
                )
            else:
                response = requests.post(
                    url, headers=headers, data=data, timeout=timeout, stream=True
                )
            with response:
                content = read_body(response, deadline)
        except (requests.exceptions.Timeout, TimeoutError) as exc:
            raise TransportTimeoutError(
                f"timed out while {operation} against {url}: no reply "
                f"{describe(timeout)} ({exc})"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ConnectionUnavailableError(
                f"could not reach {url} while {operation}: {exc}"
            ) from exc

        self.check_status_for_error(response.status_code, content, url)

        data_dict = self.decode_response(content, operation)

        if not bypass:
            self.check_response_for_error(data_dict, operation)

        return data_dict

    def authenticate(self, token: str) -> None:
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
        self._send(message, "authenticating", token=token)
        if self.token != token:
            self._refresh_token = None
        self.token = token
        self._auth_settled = True

    def invalidate(self) -> None:
        message = RequestMessage(RequestMethod.INVALIDATE)
        self.id = message.id
        self._send(message, "invalidating")
        self.token = None
        self._refresh_token = None
        self._auth_settled = True

    def signup(self, vars: dict[str, Value]) -> Tokens:
        message = RequestMessage(RequestMethod.SIGN_UP, data=vars)
        self.id = message.id
        response = self._send(message, "signup", token="")
        self.check_response_for_result(response, "signup")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        self._refresh_token = tokens.refresh
        self._auth_settled = True
        return tokens

    def signin(self, vars: dict[str, Value]) -> Tokens:
        if not self._version_learned:
            self._handshake()
        self._require_signin(vars)
        message = RequestMessage(RequestMethod.SIGN_IN, params=vars)
        self.id = message.id
        response = self._send(message, "signing in", token="")
        self.check_response_for_result(response, "signing in")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        self._refresh_token = tokens.refresh
        self._auth_settled = True
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

    def use(
        self,
        namespace: str | NullType | None = None,
        database: str | NullType | None = None,
    ) -> None:
        """Select a namespace and database.

        Either may be left out, or ``None``, to keep the current one, or
        ``Null`` to clear it.
        """
        message = RequestMessage(
            RequestMethod.USE,
            namespace=namespace,
            database=database,
        )
        self.id = message.id
        _ = self._send(message, "use")
        if namespace is not None:
            self.namespace = None if isinstance(namespace, NullType) else namespace
        if database is not None:
            self.database = None if isinstance(database, NullType) else database

    def _authorisation_due(self) -> bool:
        first = self._auth_provider is not None and not self._auth_settled
        return first or (self._renew_access and renewal_due(self.token))

    def _authorise(self) -> None:
        """Apply ``auth=`` before the first request, and renew when due.

        One thread authorises at a time; the others wait for it and then find
        nothing left to do. The requests authorising makes come back here on
        the same thread and pass straight through.
        """
        if not self._authorisation_due():
            return
        with self._auth_lock:
            if self._authorising or not self._authorisation_due():
                return
            self._authorising = True
            try:
                self._apply_auth()
            finally:
                self._authorising = False

    def _apply_auth(self) -> None:
        due = self._renew_access and renewal_due(self.token)
        if due and self._refresh_token is not None:
            if not self._version_learned:
                self._handshake()
            if self.is_feature_supported(Features.REFRESH_TOKENS):
                self.refresh()
                return
        if self._auth_provider is None:
            return
        provided = self._provided_credentials()
        if isinstance(provided, dict):
            self.signin(provided)
        elif isinstance(provided, str):
            self.authenticate(provided)
        elif provided.access is None:
            raise ValueError("auth gave Tokens with no access token to sign in with")
        else:
            self.authenticate(provided.access)
            self._refresh_token = provided.refresh

    def _provided_credentials(self) -> AuthCredentials:
        provider = self._auth_provider
        if callable(provider):
            provided = provider()
            if inspect.iscoroutine(provided):
                provided.close()
                raise TypeError(
                    "auth is a coroutine function, which only an async "
                    "connection can call; pass a plain function here"
                )
            return check_credentials(provided)
        assert provider is not None
        return provider

    def refresh(self, tokens: Tokens | None = None) -> Tokens:
        """Exchange a refresh token for a new access and refresh token.

        Uses the tokens this connection signed in with unless *tokens* is
        given, and sends the new access token from then on. The old refresh
        token is spent. Needs SurrealDB 3.0 or later.
        """
        if not self._version_learned:
            self._handshake()
        self._require(Features.REFRESH_TOKENS)
        pair = self._token_pair(tokens, "refresh()")
        message = RequestMessage(RequestMethod.REFRESH, params=[pair])
        self.id = message.id
        response = self._send(message, "refreshing the tokens", token="")
        self.check_response_for_result(response, "refreshing the tokens")
        renewed = parse_auth_result(response["result"])
        self.token = renewed.access
        self._refresh_token = renewed.refresh
        return renewed

    def revoke(self, tokens: Tokens | None = None) -> None:
        """Revoke a refresh token, so it can never be exchanged again.

        Needs SurrealDB 3.0 or later.
        """
        if not self._version_learned:
            self._handshake()
        self._require(Features.REFRESH_TOKENS)
        pair = self._token_pair(tokens, "revoke()")
        message = RequestMessage(RequestMethod.REVOKE, params=[pair])
        self.id = message.id
        self._send(message, "revoking a refresh token", token="")
        if self._refresh_token == pair["refresh"]:
            self._refresh_token = None

    def reset(self) -> None:
        """Forget the namespace, database, variables and authentication.

        Over HTTP these live on the client and are sent with each request, so
        there is nothing to tell the server. Needs SurrealDB 3.0 or later,
        like ``reset`` on the other transports.
        """
        if not self._version_learned:
            self._handshake()
        self._require(Features.SESSIONS)
        self.namespace = None
        self.database = None
        self.vars.clear()
        self.token = None
        self._refresh_token = None
        self._auth_settled = True

    def sessions(self) -> list[UUID]:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def fork_session(self, session_id: UUID | None = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def export(self, options: ExportOptions | None = None) -> str:
        """Export the selected database as SurrealQL.

        Args:
            options: What to include; the server's default without it.
                SurrealDB 2.0 takes no options.

        Example:
            sql = db.export(ExportOptions(tables=["person"], records=False))
        """
        options = options or ExportOptions()
        self._authorise()
        if not self._version_learned:
            self._handshake()
        options.check(self._server_version)
        return export_sql(
            self.url,
            options,
            effective_timeout(self, self._timeout),
            self.token,
            self.namespace,
            self.database,
        )

    def export_to(
        self, target: ExportTarget, options: ExportOptions | None = None
    ) -> None:
        """Export the selected database as SurrealQL into *target*.

        Writes the export as it arrives, so one too large to hold in memory
        can still be saved.

        Args:
            target: The path of a file to write, or a binary file object.
            options: What to include, as for :meth:`export`.

        Example:
            db.export_to("backup.surql")
        """
        options = options or ExportOptions()
        self._authorise()
        if not self._version_learned:
            self._handshake()
        options.check(self._server_version)
        export_sql_to(
            self.url,
            options,
            target,
            effective_timeout(self, self._timeout),
            self.token,
            self.namespace,
            self.database,
        )

    def import_(self, data: ImportData) -> None:
        """Import SurrealQL into the selected database.

        Args:
            data: The SurrealQL, as ``str`` or ``bytes``, or the path of a
                file holding it - such as one ``export()`` wrote. SurrealDB 3
                requires it to start with ``OPTION IMPORT;``, as exports do.

        Raises:
            ImportFailedError: if any statement failed, with each failure in
                ``failures``. The other statements were still applied.
        """
        self._authorise()
        if not self._version_learned:
            self._handshake()
        import_sql(
            self.url,
            data,
            effective_timeout(self, self._timeout),
            self.token,
            self.namespace,
            self.database,
        )

    def health(self) -> None:
        """Ask the server's ``/health`` endpoint whether it is healthy.

        :raises ConnectionUnavailableError: if it is not, or cannot be reached.
        """
        check_health(self.url, effective_timeout(self, self._timeout))

    def api(
        self,
        path: str,
        *,
        method: str = "get",
        body: Value = None,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> ApiResponse:
        """Call an endpoint defined with ``DEFINE API``.

        Sent as ``RETURN api::invoke(path, request)``. Needs SurrealDB 3.0 or
        later, started with the ``define_api`` experimental capability.

        Args:
            path: The endpoint's path, starting with ``/``.
            method: The HTTP method to invoke it with.
            body: The request body.
            headers: Request headers.
            query: Query-string parameters.

        Example:
            response = db.api("/greet", method="post", body={"name": "Ada"})
            assert response.ok
        """
        if not self._version_learned:
            self._handshake()
        self._require(Features.API)
        sql, variables = build_api_query(path, method, body, headers, query)
        return ApiResponse.from_result(self.query(sql, variables).first())

    def gql(self, query: str, vars: Mapping[str, Value] | None = None) -> list[Value]:
        """Run an ISO GQL query, such as ``MATCH (p:person) RETURN p.name``.

        Returns each statement's result, and raises the first statement that
        failed. Needs a server with the ``gql`` RPC method.
        """
        # `let()` bindings live here, not on the server, so they go with it.
        bindings = merge_query_vars(self.vars, vars)
        params: list[Value] = [query, bindings] if bindings else [query]
        message = RequestMessage(RequestMethod.GQL, params=params)
        self.id = message.id
        response = self._send(message, "gql")
        self.check_response_for_result(response, "gql")
        return statement_results(response["result"], "gql")

    def graphql(
        self,
        query: str,
        variables: Mapping[str, Value] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Value]:
        """Run a GraphQL query and return the server's ``{data, errors}``.

        Needs a server with the ``graphql`` RPC method and GraphQL enabled for
        the database, for example with ``DEFINE CONFIG GRAPHQL AUTO``.
        """
        message = RequestMessage(
            RequestMethod.GRAPHQL,
            params=graphql_params(query, variables, operation_name),
        )
        self.id = message.id
        response = self._send(message, "graphql")
        self.check_response_for_result(response, "graphql")
        result = response["result"]
        return dict(result) if isinstance(result, dict) else {"data": result}

    def _token_pair(self, tokens: Tokens | None, purpose: str) -> dict[str, str]:
        access, refresh = (
            (tokens.access, tokens.refresh)
            if tokens is not None
            else (self.token, self._refresh_token)
        )
        if refresh is None:
            raise ValueError(
                f"{purpose} needs a refresh token: pass the Tokens that signin() "
                "or signup() returned for an access method defined WITH "
                "REFRESH, or sign in with one on this connection first"
            )
        pair = {"refresh": refresh}
        if access is not None:
            pair["access"] = access
        return pair

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

    def _stream_buffered(
        self,
        query: str,
        variables: dict[str, Value],
        session_id: UUID | None,
        txn_id: UUID | None,
    ) -> list[dict[str, Any]]:
        """Run *query* the buffered way, which is all this transport can do."""
        return buffered_statements(self.query_raw(query, variables))

    def batch(self) -> Batch:
        """Statements to send together as one transaction, in one request.

        Add them with ``.query(sql, vars)`` and run them with ``.execute()``.
        They all apply or none do. Works on every transport and version.
        """
        return Batch(self)

    def query_raw(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> dict[str, Any]:
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=merge_query_vars(self.vars, vars),
        )
        self.id = message.id
        response = self._send(message, "query", bypass=True)
        return response

    def _make_executor(self) -> Any:
        """Build the executor a builder terminates through.

        ``rows()`` works here too, and hands back the buffered answer one
        row at a time - HTTP carries one response per request, so the rows
        cannot arrive early. Present so builder code moves between transports
        unchanged.
        """

        def _executor(query: str, params: dict[str, Any]) -> dict[str, Any]:
            return self.query_raw(query, params)

        def _stream(
            query: str,
            params: dict[str, Value] | None,
            *,
            require_streaming: bool = False,
            statements: bool = False,
            frames: bool = False,
        ) -> QueryStream:
            return QueryStream(
                SyncStreamOps.never_streams(self._stream_buffered, UNSUPPORTED_BY_HTTP),
                query,
                params or None,
                require_streaming=require_streaming,
                statements=statements,
                frames=frames,
            )

        return _Executor(_executor, _stream)

    # CRUD -------------------------------------------------------------------
    #
    # Passing ``data`` runs the operation immediately and returns the result;
    # the no-data form returns a builder so the caller can pick a clause.

    @overload
    def create(self, record: RecordIdType, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def create(self, record: RecordIdType, data: Value, *, into: type[M]) -> M: ...
    @overload
    def create(self, record: RecordIdType) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(self, record: RecordIdType, data: Value) -> dict[str, Value]: ...
    def create(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M] | None = None
    ) -> Any:
        """Create a record (eager).

        ``db.create(record, data)`` runs ``CREATE ... CONTENT $data``
        immediately and returns the created record (``data=None`` runs
        ``CONTENT NULL``). ``db.create(record)`` (no data) returns a
        :class:`SyncCrudBuilder` so the caller can pick a terminal clause
        (``.content`` / ``.replace`` / ``.merge`` / ``.patch`` / ``.execute``).
        Pass ``into=Model`` to map the created record onto ``Model``.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
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
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def update(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def update(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId, data: Value, *, into: type[M]
    ) -> M: ...
    @overload
    def update(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def update(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId, data: Value
    ) -> dict[str, Value]: ...
    @overload
    def update(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def update(self, record: str, data: Value) -> Value: ...
    def update(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M] | None = None
    ) -> Any:
        """Update records, replacing existing content by default (eager).

        ``db.update(record, data)`` runs eagerly and returns the result
        (``data=None`` runs ``CONTENT NULL``); the no-data form returns a
        :class:`SyncCrudBuilder` with terminal clause methods. Pass
        ``into=Model`` to map the returned record(s) onto ``Model`` /
        ``list[Model]``.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
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
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def upsert(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId, data: Value, *, into: type[M]
    ) -> M: ...
    @overload
    def upsert(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def upsert(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId, data: Value
    ) -> dict[str, Value]: ...
    @overload
    def upsert(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def upsert(self, record: str, data: Value) -> Value: ...
    def upsert(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M] | None = None
    ) -> Any:
        """Insert or update records (eager).

        ``db.upsert(record, data)`` runs eagerly and returns the result
        (``data=None`` runs ``CONTENT NULL``); the no-data form returns a
        :class:`SyncCrudBuilder` with terminal clause methods. Pass
        ``into=Model`` to map the returned record(s) onto ``Model`` /
        ``list[Model]``.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
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
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M | None]: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self, record: str, *, into: type[M]
    ) -> SyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> SyncCrudBuilder[Value]: ...
    def delete(
        self, record: RecordIdType, *, into: type[M] | None = None
    ) -> SyncCrudBuilder[Any]:
        """Delete records, returning a builder.

        A ``RecordID`` (or ``"table:id"``) returns the deleted record, or
        ``None`` when no record was deleted (matching select); a ``Table`` (or
        bare name) returns the list of deleted records. Pass ``into=Model`` to
        map the deleted record(s) onto ``Model``.
        """
        return SyncCrudBuilder(
            executor=self._make_executor(),
            operation="DELETE",
            record=record,
            op_name="delete",
            into=into,
        )

    @overload
    def insert(
        self, table: str | Table, *, relation: bool = False
    ) -> SyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self, table: str | Table, *, into: type[M], relation: bool = False
    ) -> SyncInsertBuilder[M]: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, relation: bool = False
    ) -> list[Value]: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, into: type[M], relation: bool = False
    ) -> list[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
    ) -> Any:
        """Insert record(s) or relation(s) into a table (eager).

        ``db.insert(table, data)`` runs immediately and returns the inserted
        records. ``db.insert(table)`` (no data) returns a
        :class:`SyncInsertBuilder`; pass ``relation=True`` (or chain
        ``.relation()``) for ``INSERT RELATION INTO`` and run it with
        ``.content(data)`` / ``.execute()``. Pass ``into=Model`` to map the
        inserted records onto ``list[Model]``.
        """
        builder: SyncInsertBuilder[Any] = SyncInsertBuilder(
            executor=self._make_executor(),
            table=table,
            relation=relation,
            into=into,
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
            return self.query(query, arguments).first()

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
        # Unsetting a name that was never set is not an error: the websocket
        # and embedded engines answer the `unset` RPC for an unknown key
        # without complaint, and only here did it raise `KeyError` - an
        # exception outside the `SurrealError` tree, so `except SurrealError`
        # around transport-agnostic cleanup code did not catch it.
        self.vars.pop(key, None)

    @overload
    def select(
        self,
        record: RecordID | StringRecordId,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
    ) -> SyncCrudBuilder[M | None]: ...
    @overload
    def select(
        self, record: Table, *, fields: Sequence[str] | None = None, into: type[M]
    ) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def select(
        self, record: str, *, fields: Sequence[str] | None = None, into: type[M]
    ) -> SyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def select(
        self, record: RecordID | StringRecordId, *, fields: Sequence[str] | None = None
    ) -> SyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def select(
        self, record: Table, *, fields: Sequence[str] | None = None
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def select(
        self, record: str, *, fields: Sequence[str] | None = None
    ) -> SyncCrudBuilder[Value]: ...
    def select(
        self,
        record: RecordIdType,
        *,
        fields: Sequence[str] | None = None,
        into: type[M] | None = None,
    ) -> SyncCrudBuilder[Any]:
        """Select records, returning a builder.

        A ``RecordID`` (or ``"table:id"``) returns the record dict, or ``None``
        when it is absent. A ``Table`` (or bare table-name string) returns the
        list of records. Pass ``into=Model`` to map each record onto ``Model``.

        ``fields`` narrows the projection, so the server sends only what is
        asked for rather than the whole record::

            db.select(RecordID("person", "tobie"), fields=["name", "email"])
            db.select(Table("person"), fields=["address.city"])

        A dot walks into a nested object; each segment is escaped separately, so
        a name with a space or unicode in it is quoted correctly. A field whose
        name genuinely contains a dot cannot be spelled this way - use
        :meth:`query` for that.

        Note that ``id`` is not included unless you ask for it, exactly as in
        SurrealQL. A model passed to ``into=`` that declares an ``id`` field
        therefore needs ``fields=["id", ...]``.
        """
        return SyncCrudBuilder(
            executor=self._make_executor(),
            operation="SELECT",
            record=record,
            op_name="select",
            into=into,
            fields=fields,
        )

    def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        self.id = message.id
        response = self._send(message, "getting database version", token="")
        self.check_response_for_result(response, "getting database version")
        self._adopt_server_version(response["result"])
        return response["result"]

    def connect(self, url: str | None = None) -> None:
        """Accept the connect step; HTTP opens no persistent connection.

        Requests are sent per call, so the only thing done up front is asking
        the server for its version, which is checked and remembered.
        This exists so code written against the connection API works on every
        transport - previously the inherited default raised
        ``NotImplementedError`` here while the websocket transports connected,
        so transport-agnostic code broke on HTTP alone.

        Passing *url* re-points the connection, matching the websocket
        transports.
        """
        if url is not None:
            self._forget_server_version()
            # Credentials belong to the server that issued them: none is sent
            # to the new one, and ``auth=`` is applied there afresh.
            self.token = None
            self._refresh_token = None
            self._auth_settled = False
            self.url = Url(url)
            self.raw_url = url.rstrip("/")
            self.host = self.url.hostname
            self.port = self.url.port
        if not self._version_learned:
            self._handshake()

    def close(self) -> None:
        """Close the pooled HTTP session if one is open.

        Idempotent: a no-op when no session has been opened (for example
        outside a ``with`` block) and safe to call more than once.
        """
        if self.session is not None:
            self.session.close()
        self.session = None

    def __enter__(self) -> "BlockingHttpSurrealConnection":
        """Open the pooled HTTP session if there isn't one, and return ``self``.

        Reuses an existing session rather than assigning a fresh one. The
        replaced session was never closed, so its pooled TCP connections and
        their sockets leaked - and ``__exit__`` closed only the replacement, so
        every ``with`` block entered on an already-open connection leaked one
        more. This mirrors the websocket transport, where re-entering also cost
        the server-side session.
        """
        if self.session is None:
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

    # Live queries -----------------------------------------------------------
    #
    # Refused the same way the session and transaction methods below are.
    # Inherited, they raised ``NotImplementedError`` from the template - which
    # is not a ``SurrealError``, so ``except SurrealError`` missed it even
    # though ``attach()`` beside it was covered.

    def live(self, table: str | Table, diff: bool = False) -> UUID:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    def kill(self, query_uuid: str | UUID) -> None:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    def subscribe_live(
        self, query_uuid: str | UUID
    ) -> Generator[dict[str, Value], None, None]:
        # Deliberately not a generator function: raising on the call itself
        # reports the problem where it is made, rather than on the first
        # ``next()`` somewhere further away.
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

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

    @property
    def files(self) -> BlockingFiles:
        """Typed helpers over the ``file::*`` functions - see `surrealdb.connections.files`."""
        return BlockingFiles(self)

    def relate(
        self,
        from_: RelateEnd,
        edge: RelateEdge,
        to: RelateEnd,
        data: Value = _UNSET,
    ) -> Any:
        """Relate *from_* to *to* through *edge*: ``RELATE from->edge->to``.

        *edge* is the edge table (a name or ``Table``), or a ``RecordID`` for
        an edge with a chosen id. *from_* and *to* are records, or lists of
        records to relate every pair. Pass *data* to set the edge's content.
        With *data* the edge is created at once and returned; without it, a
        builder is returned, taking ``.output()`` and ``.timeout()``, to
        finish with ``.execute()`` or ``.content(data)``.
        """
        builder: SyncCrudBuilder[Any] = relate_builder(
            SyncCrudBuilder, self._make_executor(), from_, edge, to
        )
        if data is _UNSET:
            return builder
        return builder.content(data)
