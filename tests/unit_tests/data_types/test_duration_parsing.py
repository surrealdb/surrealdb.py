"""``Duration.parse`` accepts what SurrealDB accepts, and nothing else.

The pattern was applied with ``re.findall``, which matches ``<digits><unit>``
parts *anywhere* in the string and silently ignores everything around them. So
a string the server rejects outright became a different, valid-looking
duration:

======== ================= ==============================
input    was parsed as     SurrealDB's own answer
======== ================= ==============================
``1.5s`` 5 seconds         rejected
``-1s``  +1 second         rejected
``1e3s`` 3 seconds         rejected
======== ================= ==============================

A wrong value is worse than an error here: nothing downstream can tell that
``Duration.parse("1.5s")`` did not mean five seconds, and it was stored as
five.

The accepted forms are pinned against a live server in
``test_duration_matches_the_server`` so this file cannot drift from what
SurrealDB actually parses.
"""

import pytest

from surrealdb.data.types.duration import Duration
from surrealdb.errors import InvalidDurationError

# Every one of these is rejected by SurrealDB's own `<duration>` cast.
REJECTED = [
    pytest.param("1.5s", id="fractional"),
    pytest.param("0.5h", id="fractional-hours"),
    pytest.param("-1s", id="negative"),
    pytest.param("+1s", id="explicit-plus"),
    pytest.param("1e3s", id="exponent"),
    pytest.param("1E3s", id="exponent-upper"),
    pytest.param("abc", id="not-a-duration"),
    pytest.param("", id="empty"),
    pytest.param("1s ", id="trailing-space"),
    pytest.param(" 1s", id="leading-space"),
    pytest.param("1s;DROP", id="trailing-junk"),
    pytest.param("about 1s please", id="prose"),
    pytest.param("1", id="no-unit"),
    pytest.param("s", id="no-number"),
    pytest.param("1x", id="unknown-unit"),
]

ACCEPTED = [
    pytest.param("1s", 1_000_000_000, id="seconds"),
    pytest.param("0s", 0, id="zero"),
    pytest.param("1ns", 1, id="nanoseconds"),
    pytest.param("1us", 1_000, id="microseconds-ascii"),
    pytest.param("1µs", 1_000, id="microseconds-symbol"),
    pytest.param("500ms", 500_000_000, id="milliseconds"),
    pytest.param("1h30m", 5_400_000_000_000, id="compound"),
    pytest.param("1s500ms", 1_500_000_000, id="compound-descending"),
    pytest.param("1y", 31_536_000_000_000_000, id="years"),
]


@pytest.mark.parametrize("text", REJECTED)
def test_a_string_the_server_rejects_is_rejected_here(text: str) -> None:
    with pytest.raises(InvalidDurationError):
        Duration.parse(text)


@pytest.mark.parametrize(("text", "nanoseconds"), ACCEPTED)
def test_a_string_the_server_accepts_parses_to_the_right_value(
    text: str, nanoseconds: int
) -> None:
    assert Duration.parse(text).elapsed == nanoseconds


def test_a_negative_number_of_seconds_is_rejected() -> None:
    """The integer path had the same hole: durations are unsigned."""
    with pytest.raises(InvalidDurationError):
        Duration.parse(-1)


def test_the_nanoseconds_argument_still_adds() -> None:
    """Unchanged behaviour: the offset is added to the parsed value."""
    assert Duration.parse("1s", nanoseconds=7).elapsed == 1_000_000_007
    assert Duration.parse(2, nanoseconds=7).elapsed == 2_000_000_007
