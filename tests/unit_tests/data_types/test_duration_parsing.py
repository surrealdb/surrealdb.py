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
    pytest.param("1s;DROP", id="trailing-junk"),
    pytest.param("about 1s please", id="prose"),
    pytest.param("1", id="no-unit"),
    pytest.param("s", id="no-number"),
    pytest.param("1x", id="unknown-unit"),
    # SurrealDB units are lower-case; `.lower()`-ing the input silently turned
    # each of these into a duration the server would have refused.
    pytest.param("1S", id="uppercase-seconds"),
    pytest.param("1MS", id="uppercase-millis"),
    pytest.param("1NS", id="uppercase-nanos"),
    pytest.param("1H30M", id="uppercase-compound"),
    pytest.param("1 s", id="space-before-unit"),
]

# The server accepts surrounding whitespace (`<duration>' 1s '` parses), so the
# SDK does too - these were previously asserted as rejected on nothing more than
# a guess about what the server would do.
ACCEPTED = [
    pytest.param(" 1s", 1_000_000_000, id="leading-space"),
    pytest.param("1s ", 1_000_000_000, id="trailing-space"),
    pytest.param("1s\n", 1_000_000_000, id="trailing-newline"),
    pytest.param("1s\t", 1_000_000_000, id="trailing-tab"),
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


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        pytest.param(0, (0, 0), id="zero"),
        pytest.param(1, (0, 1), id="one-nanosecond"),
        pytest.param(1_000_000_000, (1, 0), id="one-second"),
        pytest.param(1_500_000_000, (1, 500_000_000), id="one-and-a-half"),
        # The remainder is one nanosecond short of a full second, and the
        # quotient is large enough that float division rounds it up: this used
        # to split into (31536001, -1). The encoder sent that pair verbatim and
        # the server rejected the frame, so a duration the SDK parses happily
        # could be read from the database but never written back.
        pytest.param(
            31_536_000_999_999_999, (31_536_000, 999_999_999), id="1y-minus-1ns"
        ),
        pytest.param(
            999_999_999_999_999_999, (999_999_999, 999_999_999), id="very-large"
        ),
    ],
)
def test_the_wire_split_is_exact(elapsed: int, expected: tuple[int, int]) -> None:
    """``[seconds, nanoseconds]`` must be integer-exact at any magnitude.

    Nanoseconds can never be negative: the server rejects such a pair outright.
    """
    seconds, nanoseconds = Duration(elapsed).get_seconds_and_nano()

    assert (seconds, nanoseconds) == expected
    assert nanoseconds >= 0, "a negative nanosecond component is unsendable"
    assert seconds * 1_000_000_000 + nanoseconds == elapsed


def test_a_large_duration_survives_a_round_trip() -> None:
    """Decode -> encode -> decode, at a magnitude where the split used to break."""
    from surrealdb.data import cbor

    original = Duration(31_536_000_999_999_999)
    assert cbor.decode(cbor.encode(original)) == original


@pytest.mark.parametrize(
    ("elapsed", "rendered"),
    [
        pytest.param(0, "0ns", id="zero"),
        pytest.param(1_000_000_000, "1s", id="one-second"),
        pytest.param(5_400_000_000_000, "1h30m", id="compound"),
        # `divmod` floors, so a negative used to render as a value close to a
        # full year rather than as the nanosecond before zero.
        pytest.param(-1, "-1ns", id="negative"),
    ],
)
def test_rendering(elapsed: int, rendered: str) -> None:
    assert str(Duration(elapsed)) == rendered
