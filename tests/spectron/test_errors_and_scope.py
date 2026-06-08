from __future__ import annotations

import pytest

from surrealdb.spectron import (
    SpectronAPIError,
    SpectronAuthError,
    SpectronError,
    SpectronNotFoundError,
    SpectronScopeError,
)
from surrealdb.spectron._errors import error_for_status, error_from_response
from surrealdb.spectron._retry import backoff_schedule, should_retry


@pytest.mark.parametrize(
    "status, cls",
    [
        (401, SpectronAuthError),
        (403, SpectronScopeError),
        (404, SpectronNotFoundError),
        (400, SpectronAPIError),
        (422, SpectronAPIError),
        (429, SpectronAPIError),
        (500, SpectronAPIError),
        (502, SpectronAPIError),
        (418, SpectronAPIError),
    ],
)
def test_error_for_status_mapping(status: int, cls: type[SpectronAPIError]):
    exc = error_for_status(status, "boom")
    assert isinstance(exc, cls)
    assert isinstance(exc, SpectronError)
    assert exc.status_code == status
    assert exc.message == "boom"


def test_error_from_response_extracts_dict_message():
    exc = error_from_response(404, {"message": "no such doc"})
    assert isinstance(exc, SpectronNotFoundError)
    assert exc.message == "no such doc"
    assert exc.body == {"message": "no such doc"}


def test_error_from_response_falls_back_to_string_body():
    exc = error_from_response(500, "internal explosion")
    assert isinstance(exc, SpectronAPIError)
    assert exc.message == "internal explosion"


def test_error_from_response_picks_up_trace_header():
    exc = error_from_response(500, {"message": "boom"}, {"x-trace-id": "tr:1"})
    assert exc.trace_id == "tr:1"


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


def test_idempotent_post_can_retry():
    assert should_retry("POST", 503, 0, 3, idempotent=True) is True
    assert should_retry("POST", None, 0, 3, idempotent=True) is True
    assert should_retry("POST", 404, 0, 3, idempotent=True) is False
