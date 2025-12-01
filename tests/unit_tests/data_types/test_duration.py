from typing import Any

import pytest

from surrealdb.cbor import CBORTag
from surrealdb.data import cbor
from surrealdb.data.types import constants
from surrealdb.data.types.duration import Duration


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
    with pytest.raises(ValueError, match="Invalid duration format: 10x"):
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

    # Test compound duration (should use largest unit)
    compound = Duration(3600 * 1_000_000_000 + 30 * 60 * 1_000_000_000)  # 1h30m
    assert compound.to_string() == "1h"


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
