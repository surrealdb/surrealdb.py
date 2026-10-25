from __future__ import annotations

from typing import TYPE_CHECKING, Any

from surrealdb.connections.api import ApiResponse
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import (
    AsyncSurrealSession,
    AsyncSurrealTransaction,
    AsyncWsSurrealConnection,
)
from surrealdb.connections.auth_provider import AuthProvider
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import (
    BlockingSurrealSession,
    BlockingSurrealTransaction,
    BlockingWsSurrealConnection,
)
from surrealdb.connections.builders import (
    AsyncCrudBuilder,
    AsyncInsertBuilder,
    AsyncQueryBuilder,
    AsyncQueryIntoBuilder,
    AsyncRows,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
    SyncRows,
)
from surrealdb.connections.files import AsyncFiles, BlockingFiles, FileMetadata
from surrealdb.connections.import_export import ExportOptions
from surrealdb.connections.live import AsyncLiveSubscription, LiveSubscription
from surrealdb.connections.reconnect import ReconnectOptions
from surrealdb.connections.url import Url, UrlScheme
from surrealdb.data.types.datetime import Datetime, PreciseDatetime
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.file import File
from surrealdb.data.types.geometry import (
    Geometry,
    GeometryCollection,
    GeometryLine,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryPoint,
    GeometryPolygon,
)
from surrealdb.data.types.null import Null, NullType
from surrealdb.data.types.range import Bound, BoundExcluded, BoundIncluded, Range
from surrealdb.data.types.record_id import (
    RecordID,
    RecordIdValue,
    StringRecordId,
    escape_identifier,
)
from surrealdb.data.types.set import SurrealSet
from surrealdb.data.types.sized import (
    F16,
    F32,
    I8,
    I16,
    I32,
    U8,
    U16,
    U32,
    U64,
    SizedFloat,
    SizedInt,
)
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    AlreadyExistsDetailKind,
    AlreadyExistsError,
    AuthDetailKind,
    ConfigurationDetailKind,
    ConfigurationError,
    ConnectionDetailKind,
    ConnectionUnavailableError,
    ErrorKind,
    HttpStatusError,
    ImportFailedError,
    InternalError,
    InvalidDurationError,
    InvalidGeometryError,
    InvalidRecordIdError,
    InvalidTableError,
    InvalidUrlError,
    NotAllowedDetailKind,
    NotAllowedError,
    NotFoundDetailKind,
    NotFoundError,
    QueryDetailKind,
    QueryError,
    SerializationDetailKind,
    SerializationError,
    ServerError,
    SurrealDBMethodError,
    SurrealError,
    ThrownError,
    TransportError,
    TransportTimeoutError,
    UnavailableFeatureError,
    UnexpectedResponseError,
    UnsupportedEngineError,
    UnsupportedFeatureError,
    UnsupportedVersionError,
    ValidationDetailKind,
    ValidationError,
)
from surrealdb.features import (
    MAXIMUM_VERSION,
    MINIMUM_VERSION,
    Feature,
    Features,
)
from surrealdb.streaming import (
    AsyncQueryStream,
    DoneFrame,
    ErrorFrame,
    QueryStream,
    StatementResult,
    ValueFrame,
)
from surrealdb.types import Tokens, Value

# The optional native engine. Probed here, *below* the imports above, rather
# than at the top of the module: a `try`/`except ImportError` is a statement, so
# everything following it counts as an import after code (`E402`) - which is
# what kept this file exempt from the linter entirely. Nothing above depends on
# the probe, and the probe's own modules import what they need themselves, so
# the order is free.
_EMBEDDED_AVAILABLE = False
try:
    from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
    from surrealdb.connections.blocking_embedded import (
        BlockingEmbeddedSurrealConnection,
    )

    _EMBEDDED_AVAILABLE = True  # pyright: ignore[reportConstantRedefinition]
except ImportError:
    pass

if TYPE_CHECKING:
    from surrealdb.connections.async_embedded import (
        AsyncEmbeddedSurrealConnection as AsyncEmbeddedSurrealConnection,
    )
    from surrealdb.connections.blocking_embedded import (
        BlockingEmbeddedSurrealConnection as BlockingEmbeddedSurrealConnection,
    )

# Names that only exist when the optional native engine is installed
# (``pip install surrealdb[embedded]``). They are pruned from ``__all__`` below
# when it is absent, so ``from surrealdb import *`` reflects what is actually
# importable rather than advertising names that raise ``AttributeError``.
_EMBEDDED_ONLY = (
    "AsyncEmbeddedSurrealConnection",
    "BlockingEmbeddedSurrealConnection",
)

__all__ = [
    "AsyncSurreal",
    "Surreal",
    # Connections
    "AsyncHttpSurrealConnection",
    "AsyncSurrealSession",
    "AsyncSurrealTransaction",
    "AsyncWsSurrealConnection",
    "BlockingHttpSurrealConnection",
    "BlockingSurrealSession",
    "BlockingSurrealTransaction",
    "BlockingWsSurrealConnection",
    # Connection type aliases (for annotating the objects the factories return)
    "AsyncSurrealConnection",
    "BlockingSurrealConnection",
    # Builders (returned by create/update/upsert/delete/insert/query)
    "AsyncCrudBuilder",
    "AsyncInsertBuilder",
    "AsyncQueryBuilder",
    "AsyncQueryIntoBuilder",
    "SyncCrudBuilder",
    "SyncInsertBuilder",
    "SyncQueryBuilder",
    # Streaming queries (returned by a builder's rows()/statements())
    "AsyncQueryStream",
    "AsyncRows",
    "QueryStream",
    "SyncRows",
    "DoneFrame",
    "ErrorFrame",
    "StatementResult",
    "ValueFrame",
    # Data types
    "Table",
    "Duration",
    # A reference to a file in a storage bucket - bucket plus key, no contents.
    # `FileMetadata` is what `files.head()` and `files.list()` return; the two
    # `*Files` helpers are what `db.files` is, exported so they can be annotated.
    "File",
    "FileMetadata",
    "BlockingFiles",
    "AsyncFiles",
    # Same shape of mistake as `Range` below, one worse: `Geometry` is the base
    # class, so the only exported geometry name is the one that cannot be sent.
    # It constructs, then fails at encode time with "cannot encode Geometry".
    "Geometry",
    "GeometryPoint",
    "GeometryLine",
    "GeometryPolygon",
    "GeometryMultiPoint",
    "GeometryMultiLine",
    "GeometryMultiPolygon",
    "GeometryCollection",
    # `Range` was exported without its bounds, so the one exported name could
    # not actually be constructed from the public package - every range in user
    # code had to reach into `surrealdb.data.types.range` for the other half.
    "Range",
    "Bound",
    "BoundIncluded",
    "BoundExcluded",
    "ApiResponse",
    "ExportOptions",
    "AsyncLiveSubscription",
    "LiveSubscription",
    "ReconnectOptions",
    "RecordID",
    # The id types SurrealDB accepts. `RecordID.id` is deliberately wider
    # (a decoded value can be anything a server sends), so this is the name to
    # annotate or cast a value you construct against.
    "RecordIdValue",
    "StringRecordId",
    "Datetime",
    "PreciseDatetime",
    "I8",
    "U8",
    "I16",
    "U16",
    "I32",
    "U32",
    "U64",
    "F16",
    "F32",
    "SizedInt",
    "SizedFloat",
    "Null",
    "NullType",
    "SurrealSet",
    "Tokens",
    "Value",
    "escape_identifier",
    # Server versions and the features gated on them
    "Feature",
    "Features",
    "MAXIMUM_VERSION",
    "MINIMUM_VERSION",
    # Errors – base
    "SurrealError",
    # Errors – server
    "ServerError",
    "ValidationError",
    "ConfigurationError",
    "ThrownError",
    "QueryError",
    "SerializationError",
    "NotAllowedError",
    "NotFoundError",
    "AlreadyExistsError",
    "InternalError",
    "ErrorKind",
    # Error detail kind constants
    "AuthDetailKind",
    "ValidationDetailKind",
    "ConfigurationDetailKind",
    "QueryDetailKind",
    "SerializationDetailKind",
    "NotAllowedDetailKind",
    "NotFoundDetailKind",
    "AlreadyExistsDetailKind",
    "ConnectionDetailKind",
    # Errors – transport
    "TransportError",
    "ConnectionUnavailableError",
    "TransportTimeoutError",
    "HttpStatusError",
    "ImportFailedError",
    # Errors – SDK-side
    "UnsupportedEngineError",
    "UnsupportedFeatureError",
    "UnavailableFeatureError",
    "UnsupportedVersionError",
    "UnexpectedResponseError",
    "InvalidRecordIdError",
    "InvalidDurationError",
    "InvalidGeometryError",
    "InvalidTableError",
    "InvalidUrlError",
    # Errors – backward compat
    "SurrealDBMethodError",
]

_EMBEDDED_SCHEMES = (
    UrlScheme.MEM,
    UrlScheme.MEMORY,
    UrlScheme.FILE,
    UrlScheme.SURREALKV,
    UrlScheme.SURREALKV_VERSIONED,
)

# Type aliases for the connection objects the factory functions return. The
# ``Surreal``/``AsyncSurreal`` names are factory *functions*, so they cannot be
# used to annotate a connection instance (e.g. ``db: AsyncSurreal``). Use these
# unions instead: ``db: AsyncSurrealConnection`` / ``db: BlockingSurrealConnection``.
#
# Built from real classes, never from a string. A ``"..."`` member becomes a
# ``ForwardRef`` that is only resolved when something asks for the annotation at
# runtime - and it is resolved in the *caller's* namespace, never in this
# module's, so the name is not there to find. Anything that reads annotations at
# runtime therefore raised ``NameError: name 'AsyncEmbeddedSurrealConnection' is
# not defined`` from a module the caller never imported: ``typing
# .get_type_hints``, ``inspect.signature(..., eval_str=True)``, pydantic's
# ``validate_call``, and every framework that builds on them, including FastAPI
# dependency injection. It failed that way even when the embedded extra *was*
# installed, so following the advice above was enough to break a program.
#
# Without the extra the embedded classes do not exist, and neither can an
# embedded connection: ``Surreal("mem://")`` raises ``UnsupportedEngineError``.
# The union says so rather than naming a class that is not there.
if TYPE_CHECKING or _EMBEDDED_AVAILABLE:
    AsyncSurrealConnection = (
        AsyncWsSurrealConnection
        | AsyncHttpSurrealConnection
        | AsyncEmbeddedSurrealConnection
    )
    BlockingSurrealConnection = (
        BlockingWsSurrealConnection
        | BlockingHttpSurrealConnection
        | BlockingEmbeddedSurrealConnection
    )
else:
    AsyncSurrealConnection = AsyncWsSurrealConnection | AsyncHttpSurrealConnection
    BlockingSurrealConnection = (
        BlockingWsSurrealConnection | BlockingHttpSurrealConnection
    )


def Surreal(
    url: str,
    *,
    streaming: bool = True,
    ping_interval: float | None = 30.0,
    ping_timeout: float | None = 10.0,
    timeout: float | None = 30.0,
    version_check: bool = True,
    reconnect: bool | ReconnectOptions = True,
    auth: AuthProvider | None = None,
    renew_access: bool = True,
) -> BlockingSurrealConnection:
    """Open a connection to *url*, picking the transport from its scheme.

    Args:
        url: A ``ws://``, ``wss://``, ``http://``, ``https://``, ``mem://`` or
            ``file://`` address.
        streaming: Whether queries on a websocket connection may be answered as
            a stream of frames rather than one response. On by default and
            invisible - the answer is the same either way - so this only decides
            how it arrives. ``False`` puts ordinary queries back on the buffered
            path; a builder's explicit ``rows()``/``statements()`` still stream,
            since asking
            for a stream outright is taken as meaning it. Ignored by the
            transports that cannot stream.
        ping_interval: Seconds between keepalive pings on an idle websocket, or
            ``None`` to send none. Defaults to 30. Ignored by the transports that
            have no websocket.
        ping_timeout: Seconds to wait for the matching pong before the connection
            is treated as dead, or ``None`` to wait indefinitely. Defaults to 10,
            so a peer that has gone away is noticed within roughly
            ``ping_interval + ping_timeout``.
        timeout: Seconds to wait for each request's reply, or ``None`` to wait
            indefinitely. Defaults to 30. ``with db.timeout(seconds):`` overrides
            it for the requests made inside the block. Ignored by the embedded
            engine, whose requests never leave the process.
        version_check: Refuse a server outside the versions this SDK supports
            (``MINIMUM_VERSION`` up to, but not including, ``MAXIMUM_VERSION``
            in :mod:`surrealdb.features`). On by default; ``False`` connects
            anyway. Ignored by the embedded engine.
        reconnect: Whether a websocket connection reconnects on its own when
            the socket drops, replaying the namespace and database, variables,
            authentication, sessions and live queries. ``True`` (the default)
            uses the default :class:`ReconnectOptions`; pass options to tune the
            attempts and backoff, or ``False`` to turn it off. Ignored by the
            transports that have no websocket.
        auth: How the connection signs itself in: signin credentials, an
            access token, ``Tokens``, or a function returning one of those
            (a coroutine function too, for ``AsyncSurreal``). Applied when the
            connection opens and after every reconnect - see
            :mod:`surrealdb.connections.auth_provider`. Ignored by the
            embedded engine.
        renew_access: Renew the access token shortly before it expires, with
            the refresh token or else with *auth*. On by default.
    """
    constructed_url = Url(url)
    if constructed_url.scheme in _EMBEDDED_SCHEMES:
        if not _EMBEDDED_AVAILABLE:
            raise UnsupportedEngineError(url)
        return BlockingEmbeddedSurrealConnection(url=url)
    elif (
        constructed_url.scheme == UrlScheme.HTTP
        or constructed_url.scheme == UrlScheme.HTTPS
    ):
        return BlockingHttpSurrealConnection(
            url=url,
            timeout=timeout,
            version_check=version_check,
            auth=auth,
            renew_access=renew_access,
        )
    elif (
        constructed_url.scheme == UrlScheme.WS
        or constructed_url.scheme == UrlScheme.WSS
    ):
        return BlockingWsSurrealConnection(
            url=url,
            streaming=streaming,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            timeout=timeout,
            version_check=version_check,
            reconnect=reconnect,
            auth=auth,
            renew_access=renew_access,
        )
    else:
        raise UnsupportedEngineError(url)


def AsyncSurreal(
    url: str,
    *,
    streaming: bool = True,
    ping_interval: float | None = 30.0,
    ping_timeout: float | None = 10.0,
    timeout: float | None = 30.0,
    version_check: bool = True,
    reconnect: bool | ReconnectOptions = True,
    auth: AuthProvider | None = None,
    renew_access: bool = True,
) -> AsyncSurrealConnection:
    """Open a connection to *url*, picking the transport from its scheme.

    Args:
        url: A ``ws://``, ``wss://``, ``http://``, ``https://``, ``mem://`` or
            ``file://`` address.
        streaming: Whether queries on a websocket connection may be answered as
            a stream of frames rather than one response. On by default and
            invisible - the answer is the same either way - so this only decides
            how it arrives. ``False`` puts ordinary queries back on the buffered
            path; a builder's explicit ``rows()``/``statements()`` still stream,
            since asking
            for a stream outright is taken as meaning it. Ignored by the
            transports that cannot stream.
        ping_interval: Seconds between keepalive pings on an idle websocket, or
            ``None`` to send none. Defaults to 30. Ignored by the transports that
            have no websocket.
        ping_timeout: Seconds to wait for the matching pong before the connection
            is treated as dead, or ``None`` to wait indefinitely. Defaults to 10,
            so a peer that has gone away is noticed within roughly
            ``ping_interval + ping_timeout``.
        timeout: Seconds to wait for each request's reply, or ``None`` to wait
            indefinitely. Defaults to 30. ``with db.timeout(seconds):`` overrides
            it for the requests made inside the block. Ignored by the embedded
            engine, whose requests never leave the process.
        version_check: Refuse a server outside the versions this SDK supports
            (``MINIMUM_VERSION`` up to, but not including, ``MAXIMUM_VERSION``
            in :mod:`surrealdb.features`). On by default; ``False`` connects
            anyway. Ignored by the embedded engine.
        reconnect: Whether a websocket connection reconnects on its own when
            the socket drops, replaying the namespace and database, variables,
            authentication, sessions and live queries. ``True`` (the default)
            uses the default :class:`ReconnectOptions`; pass options to tune the
            attempts and backoff, or ``False`` to turn it off. Ignored by the
            transports that have no websocket.
        auth: How the connection signs itself in: signin credentials, an
            access token, ``Tokens``, or a function returning one of those
            (a coroutine function too, for ``AsyncSurreal``). Applied when the
            connection opens and after every reconnect - see
            :mod:`surrealdb.connections.auth_provider`. Ignored by the
            embedded engine.
        renew_access: Renew the access token shortly before it expires, with
            the refresh token or else with *auth*. On by default.
    """
    constructed_url = Url(url)
    if constructed_url.scheme in _EMBEDDED_SCHEMES:
        if not _EMBEDDED_AVAILABLE:
            raise UnsupportedEngineError(url)
        return AsyncEmbeddedSurrealConnection(url=url)
    elif (
        constructed_url.scheme == UrlScheme.HTTP
        or constructed_url.scheme == UrlScheme.HTTPS
    ):
        return AsyncHttpSurrealConnection(
            url=url,
            timeout=timeout,
            version_check=version_check,
            auth=auth,
            renew_access=renew_access,
        )
    elif (
        constructed_url.scheme == UrlScheme.WS
        or constructed_url.scheme == UrlScheme.WSS
    ):
        return AsyncWsSurrealConnection(
            url=url,
            streaming=streaming,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            timeout=timeout,
            version_check=version_check,
            reconnect=reconnect,
            auth=auth,
            renew_access=renew_access,
        )
    else:
        raise UnsupportedEngineError(url)


if _EMBEDDED_AVAILABLE:
    # Appended rather than pruned from a full literal, so `__all__` stays a
    # statically analyzable list for type checkers - reassigning it stops
    # pyright recognising the re-exports above and flags every one as unused.
    __all__ += [
        "AsyncEmbeddedSurrealConnection",
        "BlockingEmbeddedSurrealConnection",
    ]
else:

    def __getattr__(name: str) -> Any:
        """Explain the missing extra instead of a bare ``AttributeError``.

        Only reached for names this module does not define, so an explicit
        ``from surrealdb import BlockingEmbeddedSurrealConnection`` on an
        install without the engine says what to install.
        """
        if name in _EMBEDDED_ONLY:
            raise AttributeError(
                f"{name} requires the embedded engine, which is not installed. "
                "Install it with: pip install surrealdb[embedded]"
            )
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
