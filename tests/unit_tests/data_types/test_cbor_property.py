import pytest
from hypothesis import given
from hypothesis import strategies as st

from surrealdb.data.cbor import decode, encode


# Test roundtrip for basic types
@given(st.integers())
def test_cbor_roundtrip_int(val):
    assert decode(encode(val)) == val


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_cbor_roundtrip_float(val):
    assert decode(encode(val)) == val


@given(st.text())
def test_cbor_roundtrip_str(val):
    assert decode(encode(val)) == val


@given(st.booleans())
def test_cbor_roundtrip_bool(val):
    assert decode(encode(val)) == val


@given(st.none())
def test_cbor_roundtrip_none(val):
    assert decode(encode(val)) is None


# Test roundtrip for lists and dicts
@given(st.lists(st.integers()))
def test_cbor_roundtrip_list(val):
    assert decode(encode(val)) == val


@given(st.dictionaries(st.text(), st.integers()))
def test_cbor_roundtrip_dict(val):
    assert decode(encode(val)) == val


# Test roundtrip for nested structures
@given(
    st.recursive(
        st.integers() | st.text() | st.booleans() | st.none(),
        lambda children: st.lists(children) | st.dictionaries(st.text(), children),
        max_leaves=10,
    )
)
def test_cbor_roundtrip_nested(val):
    assert decode(encode(val)) == val


# Edge case: empty structures
@given(st.just([]))
def test_cbor_roundtrip_empty_list(val):
    assert decode(encode(val)) == val


@given(st.just({}))
def test_cbor_roundtrip_empty_dict(val):
    assert decode(encode(val)) == val
