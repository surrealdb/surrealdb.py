from __future__ import annotations

from typing import Any


class SpectronError(Exception):
    """Base class for every error raised by the Spectron SDK."""


class SpectronAPIError(SpectronError):
    """The server returned a non-2xx response we don't have a more specific class for."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        trace_id: str | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.message = message
        self.trace_id = trace_id
        self.body = body


class SpectronAuthError(SpectronAPIError):
    """401 — bearer token missing, malformed, or rejected."""


class SpectronScopeError(SpectronAPIError):
    """403 — token does not authorize the requested principal scope."""


class SpectronNotFoundError(SpectronAPIError):
    """404 — addressed entity / document / session does not exist."""


_STATUS_CLASSES: dict[int, type[SpectronAPIError]] = {
    401: SpectronAuthError,
    403: SpectronScopeError,
    404: SpectronNotFoundError,
}


def error_for_status(
    status_code: int,
    message: str,
    *,
    trace_id: str | None = None,
    body: Any = None,
) -> SpectronAPIError:
    cls = _STATUS_CLASSES.get(status_code, SpectronAPIError)
    return cls(status_code, message, trace_id=trace_id, body=body)


def error_from_response(
    status: int,
    body: Any,
    headers: dict[str, str] | None = None,
) -> SpectronAPIError:
    headers = headers or {}
    message = "Spectron request failed"
    if isinstance(body, dict):
        message = str(body.get("message") or body.get("title") or body.get("error") or message)
    elif isinstance(body, str) and body:
        message = body
    trace_id = headers.get("x-trace-id") or headers.get("X-Trace-Id")
    return error_for_status(status, message, trace_id=trace_id, body=body)


__all__ = [
    "SpectronError",
    "SpectronAPIError",
    "SpectronAuthError",
    "SpectronScopeError",
    "SpectronNotFoundError",
    "error_for_status",
    "error_from_response",
]
