"""SurrealDB stores integers as signed 64-bit; anything wider must be refused.

A Python int above the signed maximum still fits CBOR's *unsigned* range, so it
encoded cleanly and the server reinterpreted the bits. ``2**63`` came back as
``-9223372036854775808`` and ``2**64 - 1`` as ``-1``, with no error raised
anywhere - silent corruption of the value the caller stored.
"""

import pytest

from surrealdb.data.cbor import decode, encode

I64_MIN = -(2**63)
I64_MAX = 2**63 - 1


@pytest.mark.parametrize("value", [0, 1, -1, 42, I64_MIN, I64_MAX])
def test_representable_integers_round_trip(value: int) -> None:
    assert decode(encode(value)) == value


@pytest.mark.parametrize("value", [I64_MAX + 1, 2**64 - 1, 2**64, -(2**63) - 1])
def test_out_of_range_integers_are_refused(value: int) -> None:
    """Refused at encode time rather than silently wrapping on the server."""
    with pytest.raises(ValueError, match="signed 64-bit"):
        encode(value)


def test_booleans_are_unaffected() -> None:
    """``bool`` is a subclass of ``int``; the range check must not disturb it."""
    assert decode(encode(True)) is True
    assert decode(encode(False)) is False


def test_out_of_range_integer_nested_in_a_payload_is_refused() -> None:
    """The check applies wherever the integer appears, not just at the top."""
    with pytest.raises(ValueError, match="signed 64-bit"):
        encode({"outer": [{"inner": 2**63}]})
