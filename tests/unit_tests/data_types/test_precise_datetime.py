"""Nanosecond precision survives a round trip through SurrealDB.

``datetime`` resolves to microseconds, so decoding a SurrealDB timestamp used
to drop its last three digits - and writing that value back stored the
truncated form, so an ordinary read-modify-write destroyed precision *in the
database*, silently.

``PreciseDatetime`` is a ``datetime`` that keeps the remainder, so a value read
from SurrealDB can be written back unchanged.
"""

import contextlib
import copy
import datetime as dt
import os
import pickle
import time
from collections.abc import Iterator

import pytest

from surrealdb import PreciseDatetime
from surrealdb.cbor import CBORTag, dumps, loads
from surrealdb.data.cbor import decode, encode
from surrealdb.data.types import constants


def _compact(seconds: int, nanoseconds: int) -> bytes:
    """The `[seconds, nanoseconds]` frame SurrealDB sends for a datetime."""
    return dumps(CBORTag(constants.TAG_DATETIME_COMPACT, [seconds, nanoseconds]))


@contextlib.contextmanager
def _machine_timezone(name: str) -> Iterator[None]:
    """Run the block as though the machine's local timezone were *name*.

    ``TZ`` plus ``tzset()`` is what CPython reads for the local zone, which is
    what ``astimezone()`` assumes when given a naive value. CI and most
    developer machines run on UTC, where the naive-datetime bug below is
    invisible, so the zone has to be imposed rather than observed.
    """
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = previous
        time.tzset()


def test_decoding_keeps_the_sub_microsecond_remainder() -> None:
    value = decode(_compact(1767225600, 123456789))

    assert isinstance(value, PreciseDatetime)
    assert value.microsecond == 123456
    assert value.nanosecond == 789


def test_it_is_a_datetime_in_every_other_respect() -> None:
    """Existing code keeps working: this is the whole point of a subclass."""
    value = decode(_compact(1767225600, 123456789))
    equivalent = dt.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=dt.timezone.utc)

    assert isinstance(value, dt.datetime)
    assert value == equivalent
    assert value.year == 2026
    assert sorted([equivalent, value]) == [equivalent, value]
    assert pickle.loads(pickle.dumps(value)) == value
    assert copy.copy(value) == value


def test_the_wire_form_carries_all_nine_digits() -> None:
    """Re-encoding must not quietly drop what decoding preserved.

    Asserted on the raw bytes: cbor2 handles the standard datetime tag
    internally, before any tag hook, and decodes it back to a microsecond
    ``datetime`` - so neither ``loads`` nor a hook can show what was actually
    written.
    """
    value = decode(_compact(1767225600, 123456789))

    assert b"2026-01-01T00:00:00.123456789Z" in encode(value)


def test_a_plain_datetime_is_encoded_exactly_as_before() -> None:
    """The hook is registered for the subclass only, so nothing else moves."""
    plain = dt.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=dt.timezone.utc)

    assert loads(encode(plain)) == plain


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="needs a POSIX TZ database")
@pytest.mark.parametrize(
    "zone", ["UTC", "America/New_York", "Asia/Tokyo", "Australia/Adelaide"]
)
def test_a_naive_value_is_read_as_utc_whatever_the_machine_is_set_to(
    zone: str,
) -> None:
    """The same wall clock must be the same instant on every machine.

    ``astimezone`` treats a naive datetime as *local*, so this rendered a naive
    ``PreciseDatetime`` in whatever zone the host happened to be configured
    for - five hours off on a US East Coast machine, and exactly right on a UTC
    one, which is what every CI leg runs on. Nothing the caller wrote decided
    which; the host did.
    """
    with _machine_timezone(zone):
        value = PreciseDatetime(2026, 1, 1, 12, 0, 0, nanosecond=7)

        assert value.isoformat_with_nanoseconds() == "2026-01-01T12:00:00.000000007Z"


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="needs a POSIX TZ database")
@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Asia/Tokyo"])
def test_a_naive_value_agrees_with_a_naive_plain_datetime(zone: str) -> None:
    """The two spellings of "no timezone" have to mean the same instant.

    ``encode`` passes ``timezone=utc`` to cbor2, so a naive ``datetime`` has
    always gone out as UTC. A naive ``PreciseDatetime`` is the same value with
    more digits, and diverging from it turned adding precision into a silent
    change of instant.
    """
    with _machine_timezone(zone):
        naive = dt.datetime(2026, 1, 1, 12, 0, 0)
        precise = PreciseDatetime(2026, 1, 1, 12, 0, 0)

        assert loads(encode(naive)) == dt.datetime(
            2026, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc
        )
        assert precise.isoformat_with_nanoseconds().startswith("2026-01-01T12:00:00")


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="needs a POSIX TZ database")
@pytest.mark.parametrize("zone", ["UTC", "America/New_York"])
def test_an_aware_value_is_still_converted_to_utc(zone: str) -> None:
    """Reading naive values as UTC must not stop aware ones being converted."""
    with _machine_timezone(zone):
        value = PreciseDatetime(
            2026,
            1,
            1,
            12,
            0,
            0,
            tzinfo=dt.timezone(dt.timedelta(hours=5)),
            nanosecond=7,
        )

        assert value.isoformat_with_nanoseconds() == "2026-01-01T07:00:00.000000007Z"


@pytest.mark.parametrize(
    ("payload", "expected_micro", "expected_nano"),
    [
        ([1767225600, 123456789], 123456, 789),
        ([1767225600, 1], 0, 1),  # sub-microsecond only
        ([1767225600, 1000], 1, 0),  # exactly one microsecond
        ([1767225600, 0], 0, 0),
    ],
)
def test_nanosecond_splitting(
    payload: list[int], expected_micro: int, expected_nano: int
) -> None:
    value = decode(dumps(CBORTag(constants.TAG_DATETIME_COMPACT, payload)))

    assert value.microsecond == expected_micro
    assert value.nanosecond == expected_nano


def test_arithmetic_drops_the_remainder() -> None:
    """A known limit, asserted so it stays a decision rather than a surprise.

    ``datetime`` arithmetic builds the result through constructors that know
    nothing of the extra field, so a computed value carries ``nanosecond == 0``.
    Precision survives storage and retrieval, but not computation - which is
    still strictly better than before, when it survived neither.
    """
    value = decode(_compact(1767225600, 123456789))

    assert value.nanosecond == 789
    assert (value + dt.timedelta(days=1)).nanosecond == 0


def test_the_remainder_must_be_sub_microsecond() -> None:
    with pytest.raises(ValueError, match="0-999"):
        PreciseDatetime(2026, 1, 1, tzinfo=dt.timezone.utc, nanosecond=1000)
