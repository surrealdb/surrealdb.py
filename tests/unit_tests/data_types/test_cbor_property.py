import decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from surrealdb.data.cbor import decode, encode

# SurrealDB stores integers as signed 64-bit, so an unbounded strategy asks for
# a property the system cannot have. It only appeared to hold because a wider
# int encoded cleanly and was reinterpreted by the *server* - the SDK's own
# encode/decode round trip never saw the corruption. Generate what SurrealDB
# can actually represent, and assert the refusal separately below.
surreal_integers = st.integers(min_value=-(2**63), max_value=2**63 - 1)


# Test roundtrip for basic types
@given(surreal_integers)
def test_cbor_roundtrip_int(val: int) -> None:
    assert decode(encode(val)) == val


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_cbor_roundtrip_float(val: float) -> None:
    assert decode(encode(val)) == val


@given(st.text())
def test_cbor_roundtrip_str(val: str) -> None:
    assert decode(encode(val)) == val


@given(st.booleans())
def test_cbor_roundtrip_bool(val: bool) -> None:
    assert decode(encode(val)) == val


@given(st.none())
def test_cbor_roundtrip_none(val: None) -> None:
    assert decode(encode(val)) is None


# Test roundtrip for lists and dicts
@given(st.lists(surreal_integers))
def test_cbor_roundtrip_list(val: list[int]) -> None:
    assert decode(encode(val)) == val


@given(st.dictionaries(st.text(), surreal_integers))
def test_cbor_roundtrip_dict(val: dict[str, int]) -> None:
    assert decode(encode(val)) == val


# Test roundtrip for nested structures
@given(
    st.recursive(
        surreal_integers | st.text() | st.booleans() | st.none(),
        lambda children: st.lists(children) | st.dictionaries(st.text(), children),
        max_leaves=10,
    )
)
def test_cbor_roundtrip_nested(val: Any) -> None:
    assert decode(encode(val)) == val


# Edge case: empty structures
@given(st.just([]))
def test_cbor_roundtrip_empty_list(val: list[Any]) -> None:
    assert decode(encode(val)) == val


@given(st.just({}))
def test_cbor_roundtrip_empty_dict(val: dict[Any, Any]) -> None:
    assert decode(encode(val)) == val


# Test roundtrip for Decimal type
@given(
    st.decimals(
        allow_nan=False,
        allow_infinity=False,
        places=2,
        min_value=decimal.Decimal("-999999.99"),
        max_value=decimal.Decimal("999999.99"),
    )
)
def test_cbor_roundtrip_decimal(val: decimal.Decimal) -> None:
    """Test that Decimal values can be encoded and decoded via CBOR."""
    result = decode(encode(val))
    assert isinstance(result, decimal.Decimal)
    assert result == val


def test_cbor_decimal_specific_values() -> None:
    """Test specific Decimal values that are commonly used."""
    test_values = [
        decimal.Decimal("99.99"),
        decimal.Decimal("3.141592653589793"),
        decimal.Decimal("0.01"),
        decimal.Decimal("100"),
        decimal.Decimal("-42.5"),
        decimal.Decimal("0.0000001"),
        decimal.Decimal("0"),
        decimal.Decimal("-0.01"),
    ]

    for val in test_values:
        result = decode(encode(val))
        assert isinstance(result, decimal.Decimal), (
            f"Expected Decimal, got {type(result)} for value {val}"
        )
        assert result == val, f"Expected {val}, got {result}"


@given(
    st.integers(min_value=2**63) | st.integers(max_value=-(2**63) - 1),
)
def test_out_of_range_integers_are_always_refused(val: int) -> None:
    """No integer outside the signed 64-bit range may be encoded silently."""
    with pytest.raises(ValueError, match="signed 64-bit"):
        encode(val)
