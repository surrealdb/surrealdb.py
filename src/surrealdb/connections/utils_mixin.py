import re
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from surrealdb.connections.builders import (
    _is_single_record_operation,  # pyright: ignore[reportPrivateUsage]
    _resource_to_variable,  # pyright: ignore[reportPrivateUsage]
)
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ConnectionUnavailableError,
    ErrorKind,
    HttpStatusError,
    SurrealError,
    UnexpectedResponseError,
    parse_query_error,
    parse_rpc_error,
)
from surrealdb.types import Value


@contextmanager
def mapped_engine_errors(operation: str) -> Generator[None]:
    """Map the native extension's exceptions into the ``SurrealError`` tree.

    The embedded engine is a PyO3 extension, so its failures arrive as plain
    ``RuntimeError`` - including "Database connection is closed", which the
    websocket and HTTP transports report as
    :class:`~surrealdb.errors.ConnectionUnavailableError`. The same operation
    on the same SDK therefore raised a different, uncatchable exception type
    depending only on which engine was behind it.

    The original exception is preserved as ``__cause__``, so the engine's own
    message is never lost.
    """
    try:
        yield
    except SurrealError:
        # Already mapped - decoded RPC errors from the engine arrive this way.
        raise
    except RuntimeError as error:
        raise ConnectionUnavailableError(
            f"the embedded engine failed while {operation}: {error}"
        ) from error


# Legacy JSON-RPC error code historically returned by the ``info`` RPC when a
# record-authenticated session has no ROOT/NS/DB scope to report (the message
# used to read "No result found"). Newer servers surface this as a structured
# ``NotFound`` error instead; both are handled by :meth:`UtilsMixin.
# _info_needs_auth_fallback`.
_NO_RESULT_RPC_CODE = -32000

# The SurrealQL used to resolve the currently authenticated record for
# record-level ("scope") users when ``info`` reports no result.
AUTH_FALLBACK_QUERY = "SELECT * FROM $auth"

# How much of a non-2xx HTTP body to keep in the raised error message. Enough
# to identify the failure, short enough to stay readable in a traceback.
_MAX_BODY_CHARS = 300


def merge_query_vars(
    session_vars: Mapping[str, Value], call_vars: Mapping[str, Value] | None
) -> dict[str, Value]:
    """Combine ``let()`` session variables with one query's own variables.

    The HTTP transports have no server-side session to hold ``let()`` bindings,
    so they replay them as query parameters. Which side wins when a name appears
    twice is therefore an SDK decision, and it has to be the same answer the
    websocket and embedded engines give: there ``let()`` is a real RPC and the
    parameters sent with a query shadow the session binding for that query
    alone. Writing the session variables on top instead made
    ``query("RETURN $limit", {"limit": 5})`` return the ``let()`` value - the
    caller's own argument, silently ignored, on one transport only.

    The result is always a new dict. Merging into the caller's dict left
    ``let()`` bindings - including credentials someone had bound to the
    session - sitting in a dict the caller still held and might reuse.
    """
    merged: dict[str, Value] = dict(session_vars)
    if call_vars:
        merged.update(call_vars)
    return merged


# One segment of a function name that needs no quoting: `fn`, `time`, `now`.
_PLAIN_SEGMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

# Characters that cannot appear inside a backtick-quoted segment without
# ending the quoting, so a name containing one cannot be rendered safely.
_UNQUOTABLE = ("`", "\n", "\r")

# Prefix for the generated argument parameters. Distinctive so it cannot
# collide with a name someone bound with `let()`.
_RUN_ARG_PREFIX = "__surreal_run_arg"


def build_run_query(
    name: str, args: Sequence[Value] | None
) -> tuple[str, dict[str, Value]]:
    """Render ``run(name, args)`` as SurrealQL plus its bound parameters.

    The HTTP transports have no server-side session, so a variable bound with
    ``let()`` is not there for a server-side function to read - the ``run`` RPC
    carries no parameters, and the function saw nothing. The same call over a
    websocket, where ``let()`` is a real session binding, returned the value.
    One transport silently answered ``None`` where the others answered.

    Query *parameters* do reach a function body, so replaying the session
    bindings as parameters of a ``RETURN <name>(...)`` query makes HTTP behave
    the way the websocket does.

    :raises ValueError: if *name* cannot be rendered as SurrealQL. The name is
        the one part that cannot be parameter-bound, so a segment containing a
        backtick or a newline - which would end the quoting - is refused rather
        than inlined.
    :raises TypeError: if *args* is not a list or tuple. ``enumerate`` accepts
        any iterable, so a bare string used to be spread into one argument per
        character: ``run("fn::f", "ab")`` called ``f("a", "b")``. The server
        rejects a non-array ``args`` too ("Expected args to be array"), so this
        refuses the same input, just earlier and by name.
    """
    if args is not None and not isinstance(args, (list, tuple)):
        raise TypeError(
            f"run() args must be a list or tuple of values, got {type(args).__name__}"
        )
    arguments: dict[str, Value] = {
        f"{_RUN_ARG_PREFIX}{index}": value for index, value in enumerate(args or [])
    }
    rendered = ", ".join(f"${key}" for key in arguments)
    return f"RETURN {_render_function_name(name)}({rendered});", arguments


def _render_function_name(name: str) -> str:
    """Render a function name as SurrealQL, quoting segments that need it.

    SurrealDB accepts a backtick-quoted identifier in a function name, so
    ``fn::`my-fn``` is legal, definable and callable. Requiring every segment to
    be a bare identifier meant a name the ``run`` RPC executed happily was
    rejected outright the moment a ``let()`` binding pushed the call onto the
    query path - so an unrelated ``let()`` elsewhere in a program broke a
    ``run()`` call that had always worked.
    """
    if not name:
        raise ValueError("run() needs a function name, got an empty string")

    segments = name.split("::")
    rendered: list[str] = []
    for segment in segments:
        if not segment:
            raise ValueError(
                f"{name!r} is not a valid SurrealDB function name: it has an "
                "empty segment"
            )
        if _PLAIN_SEGMENT_RE.match(segment):
            rendered.append(segment)
            continue
        if any(char in segment for char in _UNQUOTABLE):
            raise ValueError(
                f"{name!r} is not a valid SurrealDB function name: the segment "
                f"{segment!r} contains a character that cannot be quoted"
            )
        rendered.append(f"`{segment}`")
    return "::".join(rendered)


def _clip(text: str) -> str:
    """Trim *text* to something that still reads as a traceback line."""
    if len(text) > _MAX_BODY_CHARS:
        return text[:_MAX_BODY_CHARS] + "..."
    return text


def _body_text(body: bytes) -> str:
    """Render an HTTP error body as short, printable text."""
    return _clip(body.decode("utf-8", errors="replace").strip())


# These are re-exported for backwards compatibility with downstream code
# that imported them via ``surrealdb.connections.utils_mixin``.
__all__ = [
    "RecordID",
    "RecordIdType",
    "SurrealError",
    "Table",
    "UtilsMixin",
    "build_run_query",
    "merge_query_vars",
]


class UtilsMixin:
    @staticmethod
    def check_response_for_error(response: dict[str, Any], process: str) -> None:
        error = response.get("error")
        if error is not None:
            raise parse_rpc_error(error)

    @staticmethod
    def check_status_for_error(status: int, body: bytes, url: str) -> None:
        """Raise when an HTTP RPC response carries a non-2xx status.

        A non-2xx ``/rpc`` response normally carries an HTTP-layer body — plain
        text or a JSON envelope — rather than the CBOR RPC envelope, so there
        is no structured error to map and the status is reported as
        :class:`HttpStatusError`. The RPC body is still tried first so that a
        server which does report a structured error alongside a non-2xx status
        keeps its ``ServerError`` mapping.
        """
        if 200 <= status < 300:
            return
        try:
            decoded = decode(body)
        except Exception:
            decoded = None
        if isinstance(decoded, dict):
            error = decoded.get("error")
            if error is not None:
                raise parse_rpc_error(error)
        raise HttpStatusError(status, _body_text(body), url)

    @staticmethod
    def decode_response(body: bytes, process: str) -> dict[str, Any]:
        """Decode a CBOR RPC envelope, or raise ``UnexpectedResponseError``.

        The envelope is always a map, and every caller reads it as one. Handing
        back whatever the body happened to hold meant a response that decoded
        to a list, a string or a number got as far as ``response.get("error")``
        and raised ``AttributeError`` - outside the ``SurrealError`` tree, so
        no documented ``except`` clause caught it, and the message named
        neither the operation nor what had actually come back.
        """
        try:
            decoded = decode(body)
        except Exception as exc:
            raise UnexpectedResponseError(
                f"could not decode the response while {process}: {exc}"
            ) from exc
        if not isinstance(decoded, dict):
            raise UnexpectedResponseError(
                f"expected a response object while {process}, got "
                f"{type(decoded).__name__}: {_clip(repr(decoded))}"
            )
        return decoded

    @staticmethod
    def check_response_for_result(response: dict[str, Any], process: str) -> None:
        if "result" not in response.keys():
            raise SurrealError(f"no result {process}: {response}")

    @staticmethod
    def _info_needs_auth_fallback(response: dict[str, Any]) -> bool:
        """Return ``True`` when an ``info`` response should fall back to ``$auth``.

        Record-level ("scope") authenticated sessions have no ROOT/NS/DB
        identity for the ``info`` RPC to report, so the server returns a
        "no result / not found" error rather than a payload. When that
        happens the caller should re-resolve the authenticated record via
        ``SELECT * FROM $auth`` so record-auth users get a consistent result
        across every transport.

        The decision is keyed on the *structured* error (``kind`` /
        legacy ``code``) rather than the human-readable message text, which
        is not part of any stability contract and varies between server
        versions.
        """
        error = response.get("error")
        if not error:
            return False
        parsed = parse_rpc_error(error)
        # New servers report this as a structured ``NotFound`` error; older
        # ones use the legacy ``-32000`` code. Match either, never the text.
        return (
            parsed.has_kind(ErrorKind.NOT_FOUND) or parsed.code == _NO_RESULT_RPC_CODE
        )

    @staticmethod
    def _extract_auth_record(auth_result: Any) -> Value | None:
        """Extract the single record from a ``SELECT * FROM $auth`` result.

        ``auth_result`` is the statement result produced by the query
        builders (a list of matching records). Returns the single
        authenticated record, or ``None`` when there is no such record so
        the caller can re-raise the original ``info`` error.
        """
        if isinstance(auth_result, list) and len(auth_result) > 0:
            return auth_result[0]
        return None

    @staticmethod
    def _check_query_result(stmt: dict[str, Any]) -> None:
        """Raise if a query statement result has ``status: "ERR"``."""
        if stmt.get("status") == "ERR":
            raise parse_query_error(stmt)

    @staticmethod
    def _is_single_record_operation(resource: RecordIdType) -> bool:
        """Whether *resource* can name at most one record.

        Single source of truth, for the same reason
        :meth:`_resource_to_variable` is one: this is the legacy ``select()``
        path's copy of the rule the builders use, and a hand-maintained
        second copy is how the two came to disagree about a ``RecordID`` whose
        id is a ``Range`` - the builders' ``delete``/``update`` dropped every
        row but the first, and so did this.
        """
        return _is_single_record_operation(resource)

    @staticmethod
    def _unwrap_result(result: Any, unwrap: bool) -> Any:
        """
        Unwraps a single-item list result if needed.

        Args:
            result: The result from the database (could be a list, dict, or other)
            unwrap: Whether to unwrap single-item lists

        Returns:
            The unwrapped result if unwrap is True and result is a single-item list,
            otherwise returns the result as-is

        Note: Returns Any because the database can return various types (dict, list, str, etc.)
        and we preserve whatever type the database sends.
        """
        # Intentionally returning Any - database results are dynamic and cannot be
        # typed more specifically without runtime schema validation
        if unwrap and isinstance(result, list) and len(result) == 1:
            return result[0]
        return result

    @staticmethod
    def _resource_to_variable(
        resource: RecordIdType, variables: dict[str, Any], var_name: str
    ) -> str:
        """Render *resource* as a variable reference inside generated SurrealQL.

        Single source of truth: this method delegates to
        :func:`surrealdb.connections.builders._resource_to_variable` so the
        legacy ``select()`` code path and the new builder pipeline can never
        diverge in their parameterisation rules.
        """
        return _resource_to_variable(resource, variables, var_name)
