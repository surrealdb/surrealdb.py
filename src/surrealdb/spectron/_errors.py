from __future__ import annotations

from typing import Any


class SpectronError(Exception):
    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        type_uri: str | None = None,
        instance: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.instance = instance
        self.extensions = extensions or {}
        message = f"[{status}] {title}"
        if detail:
            message += f": {detail}"
        super().__init__(message)


class AuthError(SpectronError):
    pass


class ScopeError(SpectronError):
    pass


class NotFoundError(SpectronError):
    pass


class ValidationError(SpectronError):
    pass


class RateLimitError(SpectronError):
    def __init__(self, *args: Any, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class ServerError(SpectronError):
    pass


_STATUS_MAP: dict[int, type[SpectronError]] = {
    400: ValidationError,
    401: AuthError,
    403: ScopeError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitError,
}


def error_from_response(
    status: int,
    body: Any,
    headers: dict[str, str] | None = None,
) -> SpectronError:
    headers = headers or {}
    title = "Spectron request failed"
    detail: str | None = None
    type_uri: str | None = None
    instance: str | None = None
    extensions: dict[str, Any] = {}

    if isinstance(body, dict):
        title = str(body.get("title") or body.get("message") or title)
        detail = body.get("detail") if isinstance(body.get("detail"), str) else None
        type_uri = body.get("type") if isinstance(body.get("type"), str) else None
        instance = body.get("instance") if isinstance(body.get("instance"), str) else None
        for key, value in body.items():
            if key not in {"status", "title", "detail", "type", "instance", "message"}:
                extensions[key] = value
    elif isinstance(body, str) and body:
        detail = body

    if status >= 500:
        cls: type[SpectronError] = ServerError
    else:
        cls = _STATUS_MAP.get(status, SpectronError)

    if cls is RateLimitError:
        retry_after: float | None = None
        raw = headers.get("Retry-After") or headers.get("retry-after")
        if raw is not None:
            try:
                retry_after = float(raw)
            except (TypeError, ValueError):
                retry_after = None
        return RateLimitError(
            status,
            title,
            detail=detail,
            type_uri=type_uri,
            instance=instance,
            extensions=extensions,
            retry_after=retry_after,
        )

    return cls(
        status,
        title,
        detail=detail,
        type_uri=type_uri,
        instance=instance,
        extensions=extensions,
    )


__all__ = [
    "SpectronError",
    "AuthError",
    "ScopeError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
    "error_from_response",
]
