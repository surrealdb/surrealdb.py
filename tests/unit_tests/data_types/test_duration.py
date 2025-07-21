import pytest

from surrealdb.data.types.duration import Duration


def test_duration_init():
    """Test Duration initialization."""
    duration = Duration(1000)
    assert duration.elapsed == 1000


def test_duration_parse_int():
    """Test Duration.parse with integer input."""
    duration = Duration.parse(5)
    assert duration.elapsed == 5 * 1_000_000_000  # 5 seconds in nanoseconds


def test_duration_parse_str_seconds():
    """Test Duration.parse with string input in seconds."""
    duration = Duration.parse("10s")
    assert duration.elapsed == 10 * 1_000_000_000


def test_duration_parse_str_minutes():
    """Test Duration.parse with string input in minutes."""
    duration = Duration.parse("2m")
    assert duration.elapsed == 2 * 60 * 1_000_000_000


def test_duration_parse_str_hours():
    """Test Duration.parse with string input in hours."""
    duration = Duration.parse("1h")
    assert duration.elapsed == 3600 * 1_000_000_000


def test_duration_parse_str_days():
    """Test Duration.parse with string input in days."""
    duration = Duration.parse("3d")
    assert duration.elapsed == 3 * 86400 * 1_000_000_000


def test_duration_parse_str_weeks():
    """Test Duration.parse with string input in weeks."""
    duration = Duration.parse("1w")
    assert duration.elapsed == 604800 * 1_000_000_000


def test_duration_parse_str_milliseconds():
    """Test Duration.parse with string input in milliseconds."""
    duration = Duration.parse("500ms")
    assert duration.elapsed == 500 * 1_000_000


def test_duration_parse_str_microseconds():
    """Test Duration.parse with string input in microseconds."""
    duration = Duration.parse("100us")
    assert duration.elapsed == 100 * 1_000


def test_duration_parse_str_nanoseconds():
    """Test Duration.parse with string input in nanoseconds."""
    duration = Duration.parse("1000ns")
    assert duration.elapsed == 1000


def test_duration_parse_invalid_unit():
    """Test Duration.parse with invalid unit raises ValueError."""
    with pytest.raises(ValueError, match="Unknown duration unit: x"):
        Duration.parse("10x")


def test_duration_parse_invalid_type():
    """Test Duration.parse with invalid type raises TypeError."""
    with pytest.raises(
        TypeError, match="Duration must be initialized with an int or str"
    ):
        # Use a list to trigger the else clause
        Duration.parse([])  # type: ignore


def test_duration_parse_with_nanoseconds():
    """Test Duration.parse with additional nanoseconds parameter."""
    duration = Duration.parse(5, nanoseconds=1000)
    assert duration.elapsed == 5 * 1_000_000_000 + 1000


def test_duration_get_seconds_and_nano():
    """Test get_seconds_and_nano method."""
    duration = Duration(2_500_000_000)  # 2.5 seconds
    seconds, nanoseconds = duration.get_seconds_and_nano()
    assert seconds == 2
    assert nanoseconds == 500_000_000


def test_duration_equality():
    """Test Duration equality."""
    duration1 = Duration(1000)
    duration2 = Duration(1000)
    duration3 = Duration(2000)

    assert duration1 == duration2
    assert duration1 != duration3
    assert duration1 != "not a duration"


def test_duration_properties():
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


def test_duration_to_string():
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

    # Test compound duration (should use largest unit)
    compound = Duration(3600 * 1_000_000_000 + 30 * 60 * 1_000_000_000)  # 1h30m
    assert compound.to_string() == "1h"


def test_duration_to_compact():
    """Test Duration.to_compact method."""
    duration = Duration(5 * 1_000_000_000)  # 5 seconds
    compact = duration.to_compact()
    assert compact == [5]
