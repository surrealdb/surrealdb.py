"""SurrealDB 4.0's bigdecimal, and how it crosses the wire."""

import copy
import pickle
from decimal import Decimal

import pytest

from surrealdb import BigDecimal
from surrealdb.data import cbor
from surrealdb.errors import UnexpectedResponseError

_PAST_DECIMAL = "79228162514264337593543950336"


def test_a_bigdecimal_keeps_its_scale_as_written() -> None:
    value = BigDecimal(f"{_PAST_DECIMAL}.50")
    assert format(value, "f") == f"{_PAST_DECIMAL}.50"
    assert repr(value) == f"BigDecimal('{_PAST_DECIMAL}.50')"


def test_a_bigdecimal_is_a_decimal() -> None:
    value = BigDecimal("1.5")
    assert isinstance(value, Decimal)
    assert value == Decimal("1.5")
    assert hash(value) == hash(Decimal("1.5"))
    assert type(value + 1) is Decimal


def test_a_bigdecimal_keeps_its_type_through_pickle_and_copy() -> None:
    value = BigDecimal("1.50")
    for twin in (
        pickle.loads(pickle.dumps(value)),
        copy.copy(value),
        copy.deepcopy(value),
    ):
        assert type(twin) is BigDecimal
        assert format(twin, "f") == "1.50"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1,5", "one"])
def test_a_value_that_is_not_a_finite_number_is_refused(value: str) -> None:
    with pytest.raises(ValueError):
        BigDecimal(value)


def test_a_bigdecimal_holds_what_postgresql_numeric_does() -> None:
    BigDecimal("1e131071")
    BigDecimal("1e-16383")
    with pytest.raises(ValueError, match="131072 digits"):
        BigDecimal("1e131072")
    with pytest.raises(ValueError, match="16383 after"):
        BigDecimal("1e-16384")


def test_a_bigdecimal_is_tag_192_over_cbor2_in_positional_notation() -> None:
    raw = cbor.encode(BigDecimal("1e40"), v2=True)
    assert raw.hex() == "d8c07829" + ("1" + "0" * 40).encode().hex()
    decoded = cbor.decode(raw, v2=True)
    assert type(decoded) is BigDecimal
    assert decoded == BigDecimal("1e40")


def test_over_plain_cbor_a_bigdecimal_that_fits_a_decimal_is_a_decimal() -> None:
    raw = cbor.encode(BigDecimal("1.50"))
    assert raw.hex() == "ca63312e35"
    assert type(cbor.decode(raw)) is Decimal


@pytest.mark.parametrize(
    "value", [_PAST_DECIMAL, "0.00000000000000000000000000001", "1e40"]
)
def test_over_plain_cbor_a_bigdecimal_past_a_decimal_is_its_text(value: str) -> None:
    raw = cbor.encode(BigDecimal(value))
    assert cbor.decode(raw) == format(BigDecimal(value), "f")


def test_a_plain_decimal_is_still_tag_10_over_cbor2() -> None:
    assert cbor.encode(Decimal("1.5"), v2=True).hex() == "ca63312e35"


@pytest.mark.parametrize("text", ["1e999999999", "١٢٣", "+1", "1.", ".5"], ids=repr)
def test_the_decoder_refuses_what_is_no_bigdecimal(text: str) -> None:
    raw = cbor.encode(text)
    tagged = bytes([0xD8, 0xC0]) + raw
    with pytest.raises(UnexpectedResponseError):
        cbor.decode(tagged, v2=True)


def test_a_bigdecimal_is_refused_outside_cbor2() -> None:
    with pytest.raises(UnexpectedResponseError, match=r"outside cbor\.2"):
        cbor.decode(bytes.fromhex("d8c06431653430"))
