from __future__ import annotations

import pytest

from surrealdb.spectron import (
    AuthError,
    NotFoundError,
    RateLimitError,
    ScopeError,
    ServerError,
    SpectronError,
    ValidationError,
    deserialise_scope,
    serialise_scope,
)
from surrealdb.spectron._errors import error_from_response
from surrealdb.spectron._retry import backoff_schedule, should_retry


def test_serialise_scope_round_trip():
    payload = serialise_scope({"org": "anneal", "user": "tobie"})
    assert payload is not None
    assert {(e["key"], e["value"]) for e in payload} == {
        ("org", "anneal"),
        ("user", "tobie"),
    }
    assert deserialise_scope(payload) == {"org": "anneal", "user": "tobie"}


def test_serialise_scope_none_passthrough():
    assert serialise_scope(None) is None
    assert deserialise_scope(None) == {}


def test_serialise_scope_coerces_non_string_values():
    payload = serialise_scope({"version": 3})  # type: ignore[dict-item]
    assert payload == [{"key": "version", "value": "3"}]


@pytest.mark.parametrize(
    "status, cls",
    [
        (400, ValidationError),
        (401, AuthError),
        (403, ScopeError),
        (404, NotFoundError),
        (422, ValidationError),
        (429, RateLimitError),
        (500, ServerError),
        (502, ServerError),
        (418, SpectronError),  # uncategorised stays on the base.
    ],
)
def test_error_from_response_status_mapping(status: int, cls: type[SpectronError]):
    exc = error_from_response(
        status,
        {"title": "boom", "detail": "kaboom", "type": "https://example", "extra": "ext"},
        {},
    )
    assert isinstance(exc, cls)
    assert exc.status == status
    assert exc.title == "boom"
    assert exc.detail == "kaboom"
    assert exc.type_uri == "https://example"
    assert exc.extensions == {"extra": "ext"}


def test_rate_limit_picks_up_retry_after():
    exc = error_from_response(429, {"title": "slow down"}, {"Retry-After": "12.5"})
    assert isinstance(exc, RateLimitError)
    assert exc.retry_after == 12.5


def test_error_from_response_falls_back_for_non_dict_bodies():
    exc = error_from_response(500, "internal explosion", {})
    assert isinstance(exc, ServerError)
    assert exc.detail == "internal explosion"


def test_backoff_schedule_capped():
    assert backoff_schedule(0) == ()
    assert backoff_schedule(1) == (0.25,)
    assert backoff_schedule(2) == (0.25, 0.5)
    assert backoff_schedule(3) == (0.25, 0.5, 1.0)
    assert backoff_schedule(10) == (0.25, 0.5, 1.0)


def test_should_retry_rules():
    assert should_retry("GET", 503, 0, 3) is True
    assert should_retry("GET", None, 0, 3) is True
    assert should_retry("GET", 404, 0, 3) is False
    assert should_retry("POST", 500, 0, 3) is False
    assert should_retry("PUT", 502, 0, 3) is False
    assert should_retry("GET", 500, 3, 3) is False
