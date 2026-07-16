"""Lifecycle tests for the blocking HTTP connection (issues #8 and #10).

These are fully mocked with ``responses`` and need no live server.
"""

from typing import Any

import pytest
import requests
import responses

import surrealdb.connections.blocking_http as blocking_http_module
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.cbor import encode

URL = "http://localhost:8000"
RPC = f"{URL}/rpc"


def _version_body(version: str = "surrealdb-2.0.0") -> bytes:
    return encode({"id": "1", "result": version})


def _register_two_versions() -> None:
    for _ in range(2):
        responses.add(
            responses.POST,
            RPC,
            body=_version_body(),
            status=200,
            content_type="application/cbor",
        )


@responses.activate
def test_pooled_session_reused_across_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single pooled session is created on entry and reused per request."""
    _register_two_versions()

    used_sessions: list[requests.Session] = []
    original_session_post = requests.Session.post

    def _spy_session_post(
        self: requests.Session, *args: Any, **kwargs: Any
    ) -> requests.Response:
        used_sessions.append(self)
        return original_session_post(self, *args, **kwargs)

    module_post_calls = {"count": 0}
    original_module_post = blocking_http_module.requests.post

    def _spy_module_post(*args: Any, **kwargs: Any) -> requests.Response:
        module_post_calls["count"] += 1
        return original_module_post(*args, **kwargs)

    monkeypatch.setattr(requests.Session, "post", _spy_session_post)
    monkeypatch.setattr(blocking_http_module.requests, "post", _spy_module_post)

    connection = BlockingHttpSurrealConnection(URL)
    with connection:
        pooled = connection.session
        assert pooled is not None
        connection.version()
        connection.version()
        assert connection.session is pooled

    # Both requests went through the same pooled session, and the
    # non-pooled ``requests.post`` fallback was never used.
    assert len(used_sessions) == 2
    assert all(s is pooled for s in used_sessions)
    assert module_post_calls["count"] == 0
    # Session closed and cleared on exit.
    assert connection.session is None


@responses.activate
def test_request_fallback_without_context_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outside a context manager requests use the ``requests.post`` fallback."""
    _register_two_versions()

    module_post_calls = {"count": 0}
    original_module_post = blocking_http_module.requests.post

    def _spy_module_post(*args: Any, **kwargs: Any) -> requests.Response:
        module_post_calls["count"] += 1
        return original_module_post(*args, **kwargs)

    monkeypatch.setattr(blocking_http_module.requests, "post", _spy_module_post)

    connection = BlockingHttpSurrealConnection(URL)
    connection.version()
    connection.version()

    assert connection.session is None
    assert module_post_calls["count"] == 2


def test_close_is_noop_on_fresh_connection() -> None:
    """close() is a safe, idempotent no-op when no session is open."""
    connection = BlockingHttpSurrealConnection(URL)
    assert connection.session is None
    connection.close()
    connection.close()
    assert connection.session is None


def test_close_closes_pooled_session() -> None:
    """close() closes an open pooled session and clears it."""
    connection = BlockingHttpSurrealConnection(URL)
    connection.session = requests.Session()
    connection.close()
    assert connection.session is None
    # Second close is still a safe no-op.
    connection.close()
