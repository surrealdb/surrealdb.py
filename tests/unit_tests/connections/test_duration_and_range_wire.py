"""What the SDK accepts as a duration or an open range matches the server.

Two defects, one shape: a value the SDK built happily and the server would not
take, or the reverse.

``Duration.parse`` used an unanchored pattern, so ``"1.5s"``, ``"-1s"`` and
``"1e3s"`` - each rejected outright by SurrealDB - parsed into a different,
wrong duration instead of raising. The server is asked here directly, so the
accepted and rejected sets cannot drift from it.

``Range`` with an open bound could be read from the server but not built by
hand: an open bound is a null on the wire, and ``None`` - the natural Python
spelling - encoded as NONE, which the server refuses inside a range. So a range
read back sent fine while the identical range written by hand was rejected.
"""

from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.null import Null
from surrealdb.data.types.range import BoundExcluded, BoundIncluded, Range
from surrealdb.errors import InvalidDurationError

DURATIONS = [
    "1s",
    "0s",
    "1ns",
    "1us",
    "1µs",
    "500ms",
    "1h30m",
    "1s500ms",
    "1y",
    # Surrounding whitespace: the server takes it, so the SDK must too.
    " 1s",
    "1s ",
    "1s\n",
    "1s\t",
]
NOT_DURATIONS = [
    "1.5s",
    "-1s",
    "1e3s",
    "0.5h",
    "1x",
    "1",
    # Units are case-sensitive on the server.
    "1S",
    "1MS",
    "1NS",
    "1H30M",
    "1 s",
]


@pytest.mark.parametrize("text", DURATIONS)
def test_the_sdk_and_the_server_agree_on_valid_durations(
    blocking_ws_connection: BlockingWsSurrealConnection, text: str
) -> None:
    """Same string, same duration, parsed on each side."""
    from_server = blocking_ws_connection.query(
        "RETURN <duration>$text;", {"text": text}
    ).first()

    assert isinstance(from_server, Duration)
    assert Duration.parse(text) == from_server


@pytest.mark.parametrize("text", NOT_DURATIONS)
def test_the_sdk_and_the_server_agree_on_invalid_durations(
    blocking_ws_connection: BlockingWsSurrealConnection, text: str
) -> None:
    """If the server will not take it, neither does ``Duration.parse``.

    The server half is asserted too: without it this test would keep passing if
    SurrealDB started accepting one of these, and the SDK would be wrong in the
    other direction.
    """
    with pytest.raises(Exception, match="(?i)cast|convert|invalid"):
        blocking_ws_connection.query("RETURN <duration>$text;", {"text": text}).first()

    with pytest.raises(InvalidDurationError):
        Duration.parse(text)


@pytest.mark.parametrize(
    ("label", "built"),
    [
        pytest.param("open end, None", Range(BoundIncluded(1), None), id="end-none"),
        pytest.param("open end, Null", Range(BoundIncluded(1), Null), id="end-null"),
        pytest.param(
            "open start, None", Range(None, BoundExcluded(5)), id="start-none"
        ),
        pytest.param(
            "open start, Null", Range(Null, BoundExcluded(5)), id="start-null"
        ),
        pytest.param("open both", Range(None, None), id="both-open"),
    ],
)
def test_a_hand_built_open_range_can_be_sent(
    blocking_ws_connection: BlockingWsSurrealConnection, label: str, built: Range
) -> None:
    returned = blocking_ws_connection.query("RETURN $r;", {"r": built}).first()

    assert returned == built, f"{label} did not survive the round trip"


def test_a_range_read_from_the_server_can_be_sent_back(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The path that worked before, so the normalisation does not break it."""
    for literal in ("1..", "..5", "1..5", "1>..=5"):
        original = blocking_ws_connection.query(f"RETURN {literal};").first()
        returned = blocking_ws_connection.query("RETURN $r;", {"r": original}).first()
        assert returned == original, f"{literal} did not survive"


def test_none_and_null_bounds_are_the_same_range() -> None:
    """Equality has to agree, or a hand-built range never matches a read one."""
    assert Range(BoundIncluded(1), None) == Range(BoundIncluded(1), Null)
    assert Range(None, None) == Range(Null, Null)
    assert hash(Range(BoundIncluded(1), None)) == hash(Range(BoundIncluded(1), Null))


def test_an_open_range_still_renders_as_surrealql() -> None:
    """``str()`` is used to build queries, so normalisation must not change it."""
    assert str(Range(BoundIncluded(1), None)) == "1.."
    assert str(Range(None, BoundExcluded(5))) == "..5"
    assert str(Range(BoundIncluded(1), BoundIncluded(5))) == "1..=5"


def test_a_range_of_record_ids_round_trips(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The shape ranges are actually used in: a record-id range on a table."""
    payload: dict[str, Any] = {"r": Range(BoundIncluded(1), None)}
    returned = blocking_ws_connection.query("RETURN $r;", payload).first()

    assert returned == payload["r"]
