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
import io
import os
import pickle
import time
from collections.abc import Iterator
from typing import Any

import pytest

from surrealdb import PreciseDatetime
from surrealdb.cbor import CBORTag, dumps
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
    """Re-encoding must not quietly drop what decoding preserved."""
    value = decode(_compact(1767225600, 123456789))

    assert encode(value) == _compact(1767225600, 123456789)


def test_a_plain_datetime_round_trips() -> None:
    plain = dt.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=dt.timezone.utc)

    assert decode(encode(plain)) == plain


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

    A naive ``datetime`` has always gone out as UTC. A naive ``PreciseDatetime`` is the same value with
    more digits, and diverging from it turned adding precision into a silent
    change of instant.
    """
    with _machine_timezone(zone):
        naive = dt.datetime(2026, 1, 1, 12, 0, 0)
        precise = PreciseDatetime(2026, 1, 1, 12, 0, 0)

        assert decode(encode(naive)) == dt.datetime(
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


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
@pytest.mark.parametrize("nanosecond", [0, 7, 789])
@pytest.mark.parametrize(
    "tzinfo", [None, dt.timezone(dt.timedelta(hours=5, minutes=30))]
)
def test_pickle_preserves_nanoseconds(
    protocol: int, nanosecond: int, tzinfo: dt.tzinfo | None
) -> None:
    value = PreciseDatetime(
        2026, 1, 1, 12, 30, 45, 123456, tzinfo=tzinfo, nanosecond=nanosecond
    )

    restored = pickle.loads(pickle.dumps(value, protocol=protocol))

    assert restored == value
    assert restored.nanosecond == nanosecond
    assert encode(restored) == encode(value)


@pytest.mark.parametrize("operation", ["copy", "deepcopy"])
@pytest.mark.parametrize("nanosecond", [0, 7, 789])
@pytest.mark.parametrize(
    "tzinfo", [None, dt.timezone(dt.timedelta(hours=5, minutes=30))]
)
def test_copy_preserves_nanoseconds(
    operation: str, nanosecond: int, tzinfo: dt.tzinfo | None
) -> None:
    value = PreciseDatetime(
        2026, 1, 1, 12, 30, 45, 123456, tzinfo=tzinfo, nanosecond=nanosecond
    )

    restored = copy.copy(value) if operation == "copy" else copy.deepcopy(value)

    assert restored is not value
    assert restored == value
    assert restored.nanosecond == nanosecond
    assert encode(restored) == encode(value)


_BETA_10_PICKLES: dict[int, bytes] = {
    0: b"csurrealdb.data.types.datetime\nPreciseDatetime\np0\n(c_codecs\nencode\np1\n(V\x07\xea\x01\x01\x0c\x1e-\x01\xe2@\np2\nVlatin1\np3\ntp4\nRp5\ntp6\nRp7\n.",
    1: b"csurrealdb.data.types.datetime\nPreciseDatetime\nq\x00(c_codecs\nencode\nq\x01(X\x0c\x00\x00\x00\x07\xc3\xaa\x01\x01\x0c\x1e-\x01\xc3\xa2@q\x02X\x06\x00\x00\x00latin1q\x03tq\x04Rq\x05tq\x06Rq\x07.",
    2: b"\x80\x02csurrealdb.data.types.datetime\nPreciseDatetime\nq\x00c_codecs\nencode\nq\x01X\x0c\x00\x00\x00\x07\xc3\xaa\x01\x01\x0c\x1e-\x01\xc3\xa2@q\x02X\x06\x00\x00\x00latin1q\x03\x86q\x04Rq\x05\x85q\x06Rq\x07.",
    3: b"\x80\x03csurrealdb.data.types.datetime\nPreciseDatetime\nq\x00C\n\x07\xea\x01\x01\x0c\x1e-\x01\xe2@q\x01\x85q\x02Rq\x03.",
    4: b"\x80\x04\x95F\x00\x00\x00\x00\x00\x00\x00\x8c\x1dsurrealdb.data.types.datetime\x94\x8c\x0fPreciseDatetime\x94\x93\x94C\n\x07\xea\x01\x01\x0c\x1e-\x01\xe2@\x94\x85\x94R\x94.",
    5: b"\x80\x05\x95F\x00\x00\x00\x00\x00\x00\x00\x8c\x1dsurrealdb.data.types.datetime\x94\x8c\x0fPreciseDatetime\x94\x93\x94C\n\x07\xea\x01\x01\x0c\x1e-\x01\xe2@\x94\x85\x94R\x94.",
}


@pytest.mark.parametrize("protocol", sorted(_BETA_10_PICKLES))
def test_a_pickle_written_before_the_remainder_was_pickled_still_loads(
    protocol: int,
) -> None:
    """Pickles from 3.0.0-beta.10 load, with the remainder they never held.

    That release pickled a ``PreciseDatetime`` as a bare ``datetime`` and
    dropped the remainder. These bytes are what it wrote, at each protocol, for
    ``PreciseDatetime(2026, 1, 1, 12, 30, 45, 123456, nanosecond=789)``. Caches,
    queues and files written by it must still load now that the remainder is
    pickled too: as a ``PreciseDatetime`` with ``nanosecond == 0``, not as an
    error or an instance missing the attribute.
    """
    restored = pickle.loads(_BETA_10_PICKLES[protocol])

    assert type(restored) is PreciseDatetime
    assert restored == dt.datetime(2026, 1, 1, 12, 30, 45, 123456)
    assert restored.nanosecond == 0
    assert encode(restored) == encode(PreciseDatetime(2026, 1, 1, 12, 30, 45, 123456))


class _Beta10PreciseDatetime(dt.datetime):
    """``PreciseDatetime`` as 3.0.0-beta.10 defined it, with no pickling of its own."""

    __slots__ = ("nanosecond",)

    nanosecond: int  # pyright: ignore[reportUninitializedInstanceVariable]

    def __new__(
        cls, *args: Any, nanosecond: int = 0, **kwargs: Any
    ) -> "_Beta10PreciseDatetime":
        instance = super().__new__(cls, *args, **kwargs)
        object.__setattr__(instance, "nanosecond", nanosecond)
        return instance


class _Beta10Unpickler(pickle.Unpickler):
    """Loads a ``PreciseDatetime`` as 3.0.0-beta.10's class, as that release would."""

    def find_class(self, module_name: str, global_name: str) -> Any:
        if (module_name, global_name) == (
            "surrealdb.data.types.datetime",
            "PreciseDatetime",
        ):
            return _Beta10PreciseDatetime
        return super().find_class(module_name, global_name)


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
@pytest.mark.parametrize("nanosecond", [0, 789])
def test_a_pickle_written_now_loads_in_3_0_0_beta_10(
    protocol: int, nanosecond: int
) -> None:
    """3.0.0-beta.10 loads today's pickles, remainder included.

    That release has no ``__setstate__``, so it applies pickled state the
    default way: a dict of attributes, or a ``(dict, slots)`` pair. State in
    any other shape fails the whole load with ``UnpicklingError`` - every value
    in the pickle, not only the datetime - so a rolling deploy or a rollback
    that shares a cache or a queue across the two versions breaks.
    """
    value = PreciseDatetime(2026, 1, 1, 12, 30, 45, 123456, nanosecond=nanosecond)

    restored = _Beta10Unpickler(
        io.BytesIO(pickle.dumps(value, protocol=protocol))
    ).load()

    assert type(restored) is _Beta10PreciseDatetime
    assert restored == value
    assert restored.nanosecond == nanosecond
