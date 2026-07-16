"""Mocked regression tests for the ``info()`` record-auth ``$auth`` fallback
over the HTTP transports (finding #23, finding #8-fragile-match).

These tests do not need a running SurrealDB server: the RPC endpoint is
mocked with ``responses`` (blocking) / ``aioresponses`` (async) and the
bodies are real CBOR payloads, so the full encode/decode + fallback path is
exercised end to end.
"""

from __future__ import annotations

from typing import Any

import pytest
import responses
from aioresponses import aioresponses

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.cbor import encode
from surrealdb.data.types.record_id import RecordID
from surrealdb.errors import NotAllowedError, ServerError
from surrealdb.types import Value

RPC_URL = "http://localhost:8000/rpc"

# A representative record-auth sign-in payload; the mocked server ignores it.
RECORD_SIGNIN: dict[str, Value] = {
    "namespace": "test_ns",
    "database": "test_db",
    "access": "user",
    "variables": {"email": "tobie@example.com", "password": "password123"},
}


def _auth_record() -> dict[str, Any]:
    return {
        "id": RecordID("user", "tobie"),
        "name": "Tobie",
        "email": "tobie@example.com",
    }


def _cbor(payload: dict[str, Any]) -> bytes:
    return encode(payload)


def _signin_ok() -> bytes:
    return _cbor({"id": "signin", "result": "a.jwt.token"})


def _info_error(error: dict[str, Any]) -> bytes:
    return _cbor({"id": "info", "error": error})


def _auth_query_result(records: list[dict[str, Any]]) -> bytes:
    return _cbor(
        {"id": "query", "result": [{"status": "OK", "result": records, "time": "1ms"}]}
    )


# Both the legacy ``-32000`` "no result found" code and the structured
# ``NotFound`` kind must trigger the fallback.
_NOT_FOUND_ERRORS = [
    pytest.param(
        {"code": -32000, "message": "No result found"}, id="legacy-code-32000"
    ),
    pytest.param(
        {"code": 0, "kind": "NotFound", "message": "There was no result"},
        id="structured-notfound-kind",
    ),
]


# --------------------------------------------------------------------------- #
# Blocking HTTP
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("error", _NOT_FOUND_ERRORS)
@responses.activate
def test_blocking_http_info_uses_auth_fallback(error: dict[str, Any]) -> None:
    record = _auth_record()
    responses.add(responses.POST, RPC_URL, body=_signin_ok(), status=200)
    responses.add(responses.POST, RPC_URL, body=_info_error(error), status=200)
    responses.add(
        responses.POST, RPC_URL, body=_auth_query_result([record]), status=200
    )

    db = BlockingHttpSurrealConnection("http://localhost:8000")
    db.signin(RECORD_SIGNIN)
    outcome = db.info()

    assert outcome == record
    assert outcome["id"] == RecordID("user", "tobie")
    # signin + info + $auth query
    assert len(responses.calls) == 3


@responses.activate
def test_blocking_http_info_non_not_found_error_raises() -> None:
    """A non not-found error must be raised, not silently swallowed, and must
    not trigger a second ``$auth`` query."""
    responses.add(responses.POST, RPC_URL, body=_signin_ok(), status=200)
    responses.add(
        responses.POST,
        RPC_URL,
        body=_info_error({"code": -32602, "message": "Not allowed"}),
        status=200,
    )

    db = BlockingHttpSurrealConnection("http://localhost:8000")
    db.signin(RECORD_SIGNIN)
    with pytest.raises(NotAllowedError):
        db.info()

    # Only signin + info: the fallback query must NOT have fired.
    assert len(responses.calls) == 2


@responses.activate
def test_blocking_http_info_empty_auth_reraises() -> None:
    """When ``$auth`` resolves to nothing, the original info error is raised."""
    responses.add(responses.POST, RPC_URL, body=_signin_ok(), status=200)
    responses.add(
        responses.POST,
        RPC_URL,
        body=_info_error({"code": -32000, "message": "No result found"}),
        status=200,
    )
    responses.add(responses.POST, RPC_URL, body=_auth_query_result([]), status=200)

    db = BlockingHttpSurrealConnection("http://localhost:8000")
    db.signin(RECORD_SIGNIN)
    with pytest.raises(ServerError):
        db.info()

    assert len(responses.calls) == 3


# --------------------------------------------------------------------------- #
# Async HTTP
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("error", _NOT_FOUND_ERRORS)
async def test_async_http_info_uses_auth_fallback(error: dict[str, Any]) -> None:
    record = _auth_record()
    with aioresponses() as mocked:
        mocked.post(RPC_URL, body=_signin_ok(), status=200)
        mocked.post(RPC_URL, body=_info_error(error), status=200)
        mocked.post(RPC_URL, body=_auth_query_result([record]), status=200)

        db = AsyncHttpSurrealConnection("http://localhost:8000")
        await db.signin(RECORD_SIGNIN)
        outcome = await db.info()

    assert outcome == record
    assert outcome["id"] == RecordID("user", "tobie")


async def test_async_http_info_non_not_found_error_raises() -> None:
    with aioresponses() as mocked:
        mocked.post(RPC_URL, body=_signin_ok(), status=200)
        mocked.post(
            RPC_URL,
            body=_info_error({"code": -32602, "message": "Not allowed"}),
            status=200,
        )

        db = AsyncHttpSurrealConnection("http://localhost:8000")
        await db.signin(RECORD_SIGNIN)
        with pytest.raises(NotAllowedError):
            await db.info()
