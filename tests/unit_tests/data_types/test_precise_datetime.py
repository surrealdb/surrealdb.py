"""Nanosecond precision survives a round trip through SurrealDB.

``datetime`` resolves to microseconds, so decoding a SurrealDB timestamp used
to drop its last three digits - and writing that value back stored the
truncated form, so an ordinary read-modify-write destroyed precision *in the
database*, silently.

``PreciseDatetime`` is a ``datetime`` that keeps the remainder, so a value read
from SurrealDB can be written back unchanged.
"""

import copy
import datetime as dt
import pickle

import pytest

from surrealdb import PreciseDatetime
from surrealdb.cbor import CBORTag, dumps, loads
from surrealdb.data.cbor import decode, encode
from surrealdb.data.types import constants


def _compact(seconds: int, nanoseconds: int) -> bytes:
    """The `[seconds, nanoseconds]` frame SurrealDB sends for a datetime."""
    return dumps(CBORTag(constants.TAG_DATETIME_COMPACT, [seconds, nanoseconds]))


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
