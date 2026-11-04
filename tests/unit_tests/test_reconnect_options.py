"""Reconnect backoff, the replay registry and connection events, without a server."""

from typing import Any
from uuid import uuid4

import pytest

from surrealdb import ReconnectOptions
from surrealdb.connections.events import EventsMixin
from surrealdb.connections.reconnect import LiveQuery, SessionRegistry


def test_defaults_match_the_js_sdk() -> None:
    options = ReconnectOptions()
    assert options.enabled
    assert options.attempts == 5
    assert options.retry_delay == 1.0
    assert options.retry_delay_max == 60.0
    assert options.retry_delay_multiplier == 2.0
    assert options.retry_delay_jitter == 0.1


@pytest.mark.parametrize(
    ("value", "enabled"),
    [(True, True), (None, True), (False, False)],
)
def test_coerce_accepts_a_bool(value: bool | None, enabled: bool) -> None:
    assert ReconnectOptions.coerce(value).enabled is enabled


def test_coerce_passes_options_through_and_refuses_anything_else() -> None:
    options = ReconnectOptions(attempts=1)
    assert ReconnectOptions.coerce(options) is options
    with pytest.raises(TypeError, match="ReconnectOptions"):
        ReconnectOptions.coerce("yes")  # type: ignore[arg-type]


def test_the_delay_grows_and_is_capped() -> None:
    options = ReconnectOptions(retry_delay=1, retry_delay_max=5, retry_delay_jitter=0)
    assert [options.delay(n) for n in range(1, 6)] == [2, 4, 5, 5, 5]


def test_jitter_stays_within_its_fraction() -> None:
    options = ReconnectOptions(retry_delay=10, retry_delay_jitter=0.1)
    for _ in range(100):
        assert 18 <= options.delay(1) <= 22


def test_attempts_bound_the_loop_unless_unlimited() -> None:
    assert ReconnectOptions(attempts=2).allows(2)
    assert not ReconnectOptions(attempts=2).allows(3)
    assert ReconnectOptions(attempts=-1).allows(10_000)
    assert not ReconnectOptions(enabled=False).allows(1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"attempts": -2},
        {"retry_delay": -1},
        {"retry_delay_max": -1},
        {"retry_delay_multiplier": -1},
        {"retry_delay_jitter": 1.5},
    ],
)
def test_invalid_options_are_refused(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ReconnectOptions(**kwargs)


def test_a_restarted_live_query_keeps_routing_to_its_original_id() -> None:
    registry = SessionRegistry()
    original = uuid4()
    live = LiveQuery(original, original, "person", False, None)
    registry.add_live(live)
    restarted = uuid4()
    registry.move_live(live, restarted)
    assert registry.logical_of(str(restarted)) == str(original)
    assert registry.logical_of(str(original)) == str(original)
    assert registry.resolve(str(original)) == str(restarted)
    registry.drop_live(str(original))
    assert registry.logical_of(str(restarted)) == str(restarted)


def test_forgetting_a_session_forgets_its_live_queries() -> None:
    registry = SessionRegistry()
    session = uuid4()
    registry.state(session).namespace = "ns"
    query = uuid4()
    registry.add_live(LiveQuery(query, query, "person", False, session))
    registry.forget_session(session)
    assert registry.sessions == {}
    assert registry.live == {}


class _Emitter(EventsMixin):
    def __init__(self) -> None:
        self._init_events()


def test_subscribe_returns_the_unsubscriber() -> None:
    emitter = _Emitter()
    heard: list[tuple[Any, ...]] = []
    unsubscribe = emitter.subscribe("error", lambda *payload: heard.append(payload))
    emitter._emit("error", "first")
    unsubscribe()
    emitter._emit("error", "second")
    assert heard == [("first",)]


def test_an_unknown_event_is_refused() -> None:
    with pytest.raises(ValueError, match="reconnecting"):
        _Emitter().subscribe("reconnected", print)  # type: ignore[arg-type]


def test_a_repeated_status_is_published_once() -> None:
    emitter = _Emitter()
    heard: list[str] = []
    emitter.subscribe("reconnecting", lambda: heard.append("reconnecting"))
    emitter._set_status("reconnecting")
    emitter._set_status("reconnecting")
    assert heard == ["reconnecting"]
    assert emitter.status == "reconnecting"


def test_a_coroutine_listener_outside_a_loop_is_closed_not_leaked() -> None:
    emitter = _Emitter()

    async def listener() -> None:
        raise AssertionError("never runs")

    emitter.subscribe("disconnected", listener)
    emitter._set_status("connected")
    emitter._set_status("disconnected")
