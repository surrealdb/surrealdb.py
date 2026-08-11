from collections.abc import AsyncGenerator
from typing import Any

import pytest

from surrealdb.cbor import CBORTag, dumps, loads
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types import constants
from surrealdb.data.types.duration import Duration
from surrealdb.errors import InvalidDurationError
from surrealdb.types import Value


def test_duration_init() -> None:
    """Test Duration initialization."""
    duration = Duration(1000)
    assert duration.elapsed == 1000


def test_duration_parse_int() -> None:
    """Test Duration.parse with integer input."""
    duration = Duration.parse(5)
    assert duration.elapsed == 5 * 1_000_000_000  # 5 seconds in nanoseconds


def test_duration_parse_str_seconds() -> None:
    """Test Duration.parse with string input in seconds."""
    duration = Duration.parse("10s")
    assert duration.elapsed == 10 * 1_000_000_000


def test_duration_parse_str_minutes() -> None:
    """Test Duration.parse with string input in minutes."""
    duration = Duration.parse("2m")
    assert duration.elapsed == 2 * 60 * 1_000_000_000


def test_duration_parse_str_hours() -> None:
    """Test Duration.parse with string input in hours."""
    duration = Duration.parse("1h")
    assert duration.elapsed == 3600 * 1_000_000_000


def test_duration_parse_str_days() -> None:
    """Test Duration.parse with string input in days."""
    duration = Duration.parse("3d")
    assert duration.elapsed == 3 * 86400 * 1_000_000_000


def test_duration_parse_str_weeks() -> None:
    """Test Duration.parse with string input in weeks."""
    duration = Duration.parse("1w")
    assert duration.elapsed == 604800 * 1_000_000_000


def test_duration_parse_str_years() -> None:
    """Test Duration.parse with string input in years."""
    duration = Duration.parse("2y")
    assert duration.elapsed == 2 * 365 * 86400 * 1_000_000_000


def test_duration_parse_str_milliseconds() -> None:
    """Test Duration.parse with string input in milliseconds."""
    duration = Duration.parse("500ms")
    assert duration.elapsed == 500 * 1_000_000


def test_duration_parse_str_microseconds() -> None:
    """Test Duration.parse with string input in microseconds (both us and µs variants)."""
    duration_us = Duration.parse("100us")
    duration_mu = Duration.parse("100µs")

    # Both should equal 100 microseconds in nanoseconds
    assert duration_us.elapsed == 100 * 1_000
    assert duration_mu.elapsed == 100 * 1_000

    # Both variants should produce identical results
    assert duration_us.elapsed == duration_mu.elapsed


def test_duration_parse_str_compound() -> None:
    """Test Duration.parse with comprehensive compound duration including all units."""
    duration = Duration.parse("1y2w3d4h5m6s7ms8us9ns")
    assert (
        duration.elapsed
        == (1 * 365 * 86400 * 1_000_000_000)
        + (2 * 604800 * 1_000_000_000)
        + (3 * 86400 * 1_000_000_000)
        + (4 * 3600 * 1_000_000_000)
        + (5 * 60 * 1_000_000_000)
        + (6 * 1_000_000_000)
        + (7 * 1_000_000)
        + (8 * 1_000)
        + 9
    )


def test_duration_parse_str_nanoseconds() -> None:
    """Test Duration.parse with string input in nanoseconds."""
    duration = Duration.parse("1000ns")
    assert duration.elapsed == 1000


def test_duration_parse_invalid_unit() -> None:
    """Test Duration.parse with invalid unit raises ValueError."""
    # it fails when checking the format, before checking if the unit is valid,
    # which is ok.
    with pytest.raises(InvalidDurationError, match="Invalid duration format: 10x"):
        Duration.parse("10x")


def test_duration_parse_with_nanoseconds() -> None:
    """Test Duration.parse with additional nanoseconds parameter."""
    duration = Duration.parse(5, nanoseconds=1000)
    assert duration.elapsed == 5 * 1_000_000_000 + 1000


def test_duration_get_seconds_and_nano() -> None:
    """Test get_seconds_and_nano method."""
    duration = Duration(2_500_000_000)  # 2.5 seconds
    seconds, nanoseconds = duration.get_seconds_and_nano()
    assert seconds == 2
    assert nanoseconds == 500_000_000


def test_duration_equality() -> None:
    """Test Duration equality."""
    duration1 = Duration(1000)
    duration2 = Duration(1000)
    duration3 = Duration(2000)

    assert duration1 == duration2
    assert duration1 != duration3
    assert duration1 != "not a duration"


def test_duration_hashable() -> None:
    """Duration defines __eq__, so it must define a consistent __hash__ to
    remain usable as a dict key / set member (issue #9)."""
    duration1 = Duration(1000)
    duration2 = Duration(1000)

    assert hash(duration1) == hash(duration2)
    assert duration1 in {duration2}
    assert {duration1: "value"}[Duration(1000)] == "value"


def test_duration_properties() -> None:
    """Test Duration property accessors."""
    # 1 hour, 30 minutes, 45 seconds, 500 milliseconds, 100 microseconds, 50 nanoseconds
    total_ns = (
        (3600 + 30 * 60 + 45) * 1_000_000_000 + 500 * 1_000_000 + 100 * 1_000 + 50
    )
    duration = Duration(total_ns)

    assert duration.nanoseconds == total_ns
    assert duration.microseconds == total_ns // 1_000
    assert duration.milliseconds == total_ns // 1_000_000
    assert duration.seconds == total_ns // 1_000_000_000
    assert duration.minutes == total_ns // (60 * 1_000_000_000)
    assert duration.hours == total_ns // (3600 * 1_000_000_000)
    assert duration.days == total_ns // (86400 * 1_000_000_000)
    assert duration.weeks == total_ns // (604800 * 1_000_000_000)
    assert duration.years == total_ns // (365 * 86400 * 1_000_000_000)


def test_duration_to_string() -> None:
    """Test Duration.to_string method."""
    # Test various durations
    assert Duration(0).to_string() == "0ns"
    assert Duration(1000).to_string() == "1us"  # 1000ns = 1us
    assert Duration(1_000_000).to_string() == "1ms"
    assert Duration(1_000_000_000).to_string() == "1s"
    assert Duration(60 * 1_000_000_000).to_string() == "1m"
    assert Duration(3600 * 1_000_000_000).to_string() == "1h"
    assert Duration(86400 * 1_000_000_000).to_string() == "1d"
    assert Duration(604800 * 1_000_000_000).to_string() == "1w"
    assert Duration(365 * 86400 * 1_000_000_000).to_string() == "1y"

    # Test compound duration (should combine all non-zero units, largest first)
    compound = Duration(3600 * 1_000_000_000 + 30 * 60 * 1_000_000_000)  # 1h30m
    assert compound.to_string() == "1h30m"


def test_duration_to_string_compound_all_units() -> None:
    """Test Duration.to_string with every unit non-zero, matching the parser's
    own compound format (see test_duration_parse_str_compound) and the
    server/JS/PHP SDKs' Display implementations."""
    elapsed = (
        (1 * 365 * 86400 * 1_000_000_000)
        + (2 * 604800 * 1_000_000_000)
        + (3 * 86400 * 1_000_000_000)
        + (4 * 3600 * 1_000_000_000)
        + (5 * 60 * 1_000_000_000)
        + (6 * 1_000_000_000)
        + (7 * 1_000_000)
        + (8 * 1_000)
        + 9
    )
    assert Duration(elapsed).to_string() == "1y2w3d4h5m6s7ms8us9ns"


def test_duration_str() -> None:
    """Test Duration.__str__ produces the same SurrealQL literal as to_string()."""
    assert str(Duration(0)) == "0ns"
    assert str(Duration(1000)) == "1us"
    compound = Duration(3600 * 1_000_000_000 + 30 * 60 * 1_000_000_000)  # 1h30m
    assert str(compound) == compound.to_string() == "1h30m"


def test_duration_to_compact() -> None:
    """Test Duration.to_compact method."""
    duration = Duration(5 * 1_000_000_000)  # 5 seconds
    compact = duration.to_compact()
    assert compact == [5]


def test_duration_cbor_decode_compact_single_element() -> None:
    """Test CBOR decoding of TAG_DURATION_COMPACT with single element array."""
    # Simulate server sending [seconds] only (no nanoseconds)
    tag = CBORTag(constants.TAG_DURATION_COMPACT, [3600])  # 1 hour in seconds

    # tag_decoder doesn't actually use the decoder parameter for durations
    result = cbor.tag_decoder(None, tag)

    assert isinstance(result, Duration)
    assert result.elapsed == 3600 * 1_000_000_000  # 1 hour in nanoseconds


def test_duration_cbor_decode_compact_dual_element() -> None:
    """Test CBOR decoding of TAG_DURATION_COMPACT with dual element array."""
    # Simulate server sending [seconds, nanoseconds]
    tag = CBORTag(constants.TAG_DURATION_COMPACT, [2, 500_000_000])  # 2.5 seconds

    # tag_decoder doesn't actually use the decoder parameter for durations
    result = cbor.tag_decoder(None, tag)

    assert isinstance(result, Duration)
    assert result.elapsed == 2_500_000_000  # 2.5 seconds in nanoseconds


def test_duration_cbor_encode_decode_roundtrip() -> None:
    """Test encoding and decoding Duration through CBOR."""
    # Create duration with both seconds and nanoseconds
    original = Duration(2_500_000_000)  # 2.5 seconds in nanoseconds

    # Encode
    encoded = cbor.encode(original)

    # Decode
    decoded = cbor.decode(encoded)

    assert isinstance(decoded, Duration)
    assert decoded == original

    # Test with whole seconds (no fractional nanoseconds)
    original_whole = Duration(5_000_000_000)  # 5 seconds
    encoded_whole = cbor.encode(original_whole)
    decoded_whole = cbor.decode(encoded_whole)

    assert isinstance(decoded_whole, Duration)
    assert decoded_whole == original_whole


def test_duration_encodes_with_the_compact_tag() -> None:
    """A ``Duration`` goes on the wire as tag 14 with ``[seconds, nanos]``.

    Tag 13 carries the *string* form (``"1h30m"``); tag 14 carries the compact
    ``[seconds, nanoseconds]`` array. The encoder previously paired tag 13 with
    the array payload, which the server rejects with HTTP 400 - a ``Duration``
    could be read back but never sent, on every transport and engine.

    Asserted on the emitted tag rather than through a round trip, because the
    SDK's own decoder accepts either shape: an encode/decode round trip passes
    with the wrong tag, which is how this survived four releases.
    """
    raw = loads(cbor.encode(Duration.parse("1h30m")))

    assert isinstance(raw, CBORTag), f"expected a tagged value, got {raw!r}"
    assert raw.tag == constants.TAG_DURATION_COMPACT, (
        f"expected tag {constants.TAG_DURATION_COMPACT} (TAG_DURATION_COMPACT), "
        f"got {raw.tag}"
    )
    assert list(raw.value) == [5400, 0]


# Database fixture


@pytest.fixture
async def surrealdb_connection() -> AsyncGenerator[AsyncWsSurrealConnection, None]:
    url = "ws://localhost:8000/rpc"
    vars_params: dict[str, Value] = {"username": "root", "password": "root"}
    connection = AsyncWsSurrealConnection(url)
    await connection.signin(vars_params)
    await connection.use(namespace="test_ns", database="test_db")
    await connection.query("DEFINE TABLE duration_tests SCHEMALESS;")
    await connection.query("DELETE duration_tests;")
    yield connection
    await connection.query("REMOVE TABLE IF EXISTS duration_tests;")
    await connection.close()


@pytest.mark.asyncio
async def test_duration_db_roundtrip(surrealdb_connection: Any) -> None:
    """A ``Duration`` survives a trip through a real server.

    Nothing sent a ``Duration`` to a server before, which is how the wrong CBOR
    tag shipped: it was rejected with HTTP 400 on every write while the
    in-process encode/decode round trip passed. This runs against every server
    version in the CI matrix, so a tag the server does not accept fails here.
    """
    original = Duration.parse("1h30m")

    await surrealdb_connection.query(
        "CREATE duration_tests:test1 SET value = $val;", vars={"val": original}
    )
    result = await surrealdb_connection.query("SELECT * FROM duration_tests;").first()

    assert result[0]["value"] == original


def test_zero_duration_decodes_from_an_empty_array() -> None:
    """The server sends a zero duration as tag 14 with an EMPTY array.

    The decoder handled one and two elements and indexed ``[0]`` otherwise, so
    a zero duration raised ``IndexError`` and destroyed the whole response -
    not just that field. Ordinary expressions produce one.
    """
    assert cbor.decode(dumps(CBORTag(constants.TAG_DURATION_COMPACT, []))) == Duration(0)

    # And it still round-trips through the SDK's own encoder.
    assert cbor.decode(cbor.encode(Duration(0))) == Duration(0)
