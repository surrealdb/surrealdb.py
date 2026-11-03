"""The sized number kinds of SurrealDB 4.0, and how they cross the wire."""

import math
import struct

import pytest

from surrealdb.cbor import CBORTag, dumps
from surrealdb.data import cbor
from surrealdb.data.types import constants
from surrealdb.data.types.sized import F16, F32
from surrealdb.errors import UnexpectedResponseError


def test_f32_rounds_to_its_width_as_a_cast_does() -> None:
    value = F32(0.1)
    assert type(value) is F32
    assert float(value) == struct.unpack("<f", struct.pack("<f", 0.1))[0]
    assert float(value) == 0.10000000149011612


def test_f16_rounds_to_its_width_as_a_cast_does() -> None:
    assert float(F16(0.1)) == struct.unpack("<e", struct.pack("<e", 0.1))[0]
    assert float(F16("1.1")) == struct.unpack("<e", struct.pack("<e", 1.1))[0]


@pytest.mark.parametrize(
    ("kind", "value"), [(F32, 1e40), (F32, -1e40), (F16, 70_000.0)]
)
def test_a_value_too_large_for_the_width_is_refused(
    kind: type[F16] | type[F32], value: float
) -> None:
    with pytest.raises(ValueError, match="outside the"):
        kind(value)


def test_infinities_and_nan_are_kept() -> None:
    assert F32(math.inf) == math.inf
    assert F16(-math.inf) == -math.inf
    assert math.isnan(F32(math.nan))


def test_a_rounded_f32_round_trips_over_cbor2() -> None:
    decoded = cbor.decode(cbor.encode(F32(0.1), v2=True), v2=True)
    assert type(decoded) is F32
    assert decoded == F32(0.1)


def test_the_decoder_still_refuses_a_value_the_width_cannot_hold() -> None:
    raw = dumps(CBORTag(constants.TAG_F32, 0.1))
    with pytest.raises(UnexpectedResponseError, match="cannot hold exactly"):
        cbor.decode(raw, v2=True)
