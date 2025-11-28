import decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from surrealdb.data.cbor import decode, encode


# Test roundtrip for basic types
@given(st.integers())
def test_cbor_roundtrip_int(val) -> None:
    assert decode(encode(val)) == val


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_cbor_roundtrip_float(val) -> None:
    assert decode(encode(val)) == val


@given(st.text())
def test_cbor_roundtrip_str(val) -> None:
    assert decode(encode(val)) == val


@given(st.booleans())
def test_cbor_roundtrip_bool(val) -> None:
    assert decode(encode(val)) == val


@given(st.none())
def test_cbor_roundtrip_none(val) -> None:
    assert decode(encode(val)) is None


# Test roundtrip for lists and dicts
@given(st.lists(st.integers()))
def test_cbor_roundtrip_list(val) -> None:
    assert decode(encode(val)) == val


@given(st.dictionaries(st.text(), st.integers()))
def test_cbor_roundtrip_dict(val) -> None:
    assert decode(encode(val)) == val


# Test roundtrip for nested structures
@given(
    st.recursive(
        st.integers() | st.text() | st.booleans() | st.none(),
        lambda children: st.lists(children) | st.dictionaries(st.text(), children),
        max_leaves=10,
    )
)
def test_cbor_roundtrip_nested(val) -> None:
    assert decode(encode(val)) == val


# Edge case: empty structures
@given(st.just([]))
def test_cbor_roundtrip_empty_list(val) -> None:
    assert decode(encode(val)) == val


@given(st.just({}))
def test_cbor_roundtrip_empty_dict(val) -> None:
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
def test_cbor_roundtrip_decimal(val) -> None:
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
