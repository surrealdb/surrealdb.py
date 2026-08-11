"""``authenticate()`` sends the token without adopting it.

The token has to reach the server on the ``authenticate`` request - that is how
it always went out, and preserving it keeps the successful path byte-identical
across every server version in the support matrix. What changed is that the
connection no longer *keeps* it until the server has accepted it, so a refusal
cannot leave a bad token attached to everything that follows.

Driven through fake transports so the headers can be inspected directly; no
server involved.
"""

from typing import Any

import pytest

from surrealdb.connections import blocking_http
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.cbor import encode

HTTP_URL = "http://localhost:8000"
GOOD_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.Zm9vYmFyYmF6"
OTHER_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJiIn0.cXV4cXV1eHF1dXg"


class _FakeResponse:
    status_code = 200

    def __init__(self) -> None:
        self.content = encode({"id": "1", "result": None})


@pytest.fixture
def captured_headers(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Capture the headers of every blocking HTTP request."""
    seen: list[dict[str, str]] = []

    def _post(url: str, **kwargs: Any) -> _FakeResponse:
        seen.append(dict(kwargs["headers"]))
        return _FakeResponse()

    monkeypatch.setattr(blocking_http.requests, "post", _post)
    return seen


def test_authenticate_sends_the_token_it_was_given(
    captured_headers: list[dict[str, str]],
) -> None:
    connection = BlockingHttpSurrealConnection(HTTP_URL)

    connection.authenticate(GOOD_TOKEN)

    assert captured_headers[0]["Authorization"] == f"Bearer {GOOD_TOKEN}"


def test_authenticate_sends_the_new_token_not_the_held_one(
    captured_headers: list[dict[str, str]],
) -> None:
    """Swapping identities authorises the request with the *incoming* token."""
    connection = BlockingHttpSurrealConnection(HTTP_URL)
    connection.token = OTHER_TOKEN

    connection.authenticate(GOOD_TOKEN)

    assert captured_headers[0]["Authorization"] == f"Bearer {GOOD_TOKEN}"


def test_the_override_does_not_leak_into_later_requests(
    captured_headers: list[dict[str, str]],
) -> None:
    """It authorises one request; afterwards the connection's own token rules."""
    connection = BlockingHttpSurrealConnection(HTTP_URL)
    connection.token = OTHER_TOKEN

    connection.authenticate(GOOD_TOKEN)
    connection.query_raw("RETURN 1")

    # The second request carries the token authenticate adopted on success.
    assert connection.token == GOOD_TOKEN
    assert captured_headers[1]["Authorization"] == f"Bearer {GOOD_TOKEN}"


def test_a_failed_send_leaves_the_held_token_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The assignment sits after the request, so a raise skips it."""

    def _explode(url: str, **kwargs: Any) -> _FakeResponse:
        raise blocking_http.requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr(blocking_http.requests, "post", _explode)
    connection = BlockingHttpSurrealConnection(HTTP_URL)
    connection.token = OTHER_TOKEN

    with pytest.raises(Exception):
        connection.authenticate(GOOD_TOKEN)

    assert connection.token == OTHER_TOKEN


async def test_async_authenticate_sends_the_token_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = AsyncHttpSurrealConnection(HTTP_URL)
    seen: list[dict[str, str]] = []

    async def _request(
        session: Any,
        url: str,
        headers: dict[str, str],
        data: bytes,
        operation: str,
        bypass: bool,
    ) -> dict[str, Any]:
        seen.append(dict(headers))
        return {"id": "1", "result": None}

    monkeypatch.setattr(connection, "_request", _request)
    connection.token = OTHER_TOKEN

    await connection.authenticate(GOOD_TOKEN)

    assert seen[0]["Authorization"] == f"Bearer {GOOD_TOKEN}"
    assert connection.token == GOOD_TOKEN
