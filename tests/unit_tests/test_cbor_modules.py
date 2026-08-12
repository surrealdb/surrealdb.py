import decimal
import importlib
import uuid

import pytest

from surrealdb import cbor as cbor_pkg
from surrealdb.cbor import (
    CBORDecoder,
    CBOREncoder,
    CBORTag,
    dumps,
    loads,
)
from surrealdb.data import cbor
from surrealdb.data.types import constants
from surrealdb.data.types.null import Null


def test_public_cbor_api_exports() -> None:
    """The public ``surrealdb.cbor`` package re-exports the real cbor2 API."""
    for name in (
        "CBORDecoder",
        "CBOREncoder",
        "CBORTag",
        "dumps",
        "loads",
        "dump",
        "load",
        "shareable_encoder",
        "CBORError",
        "CBORDecodeError",
        "CBOREncodeError",
        "CBORSimpleValue",
        "FrozenDict",
        "undefined",
    ):
        assert hasattr(cbor_pkg, name), f"missing export: {name}"


def test_public_cbor_dumps_loads_roundtrip() -> None:
    """The re-exported ``dumps``/``loads`` round-trip plain data."""
    payload = {"a": 1, "b": [1, 2, 3], "c": "hello"}
    encoded = dumps(payload)
    assert isinstance(encoded, bytes)
    assert loads(encoded) == payload


def test_public_cbor_tag_roundtrip() -> None:
    """``CBORTag`` survives a dumps/loads round-trip via the public API."""
    tag = CBORTag(88, [1.0, 2.0])
    decoded = loads(dumps(tag))
    assert isinstance(decoded, CBORTag)
    assert decoded.tag == 88
    assert decoded.value == [1.0, 2.0]


def test_encoder_decoder_classes_are_exported() -> None:
    """The encoder/decoder classes are importable from the public package."""
    assert isinstance(CBOREncoder, type)
    assert isinstance(CBORDecoder, type)


@pytest.mark.parametrize(
    "module_name",
    [
        "surrealdb.cbor.decoder",
        "surrealdb.cbor.encoder",
        "surrealdb.cbor.types",
        "surrealdb.cbor.tool",
    ],
)
def test_dead_cbor_shim_modules_are_removed(module_name: str) -> None:
    """The old re-export shim / CLI modules no longer exist."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


# ---------------------------------------------------------------------------
# SurrealDB CBOR encode/decode round-trips (surrealdb.data.cbor)
# ---------------------------------------------------------------------------


def test_set_encodes_with_surreal_set_tag() -> None:
    """Sets encode with SurrealDB's set tag (56), not native cbor tag 258."""
    encoded = cbor.encode({1, 2, 3})
    # Tag 56 -> major type 6 with a 1-byte argument: 0xd8 0x38.
    assert encoded[:2] == b"\xd8\x38"
    # It must NOT be native tag 258 (0xd9 0x01 0x02).
    assert encoded[:3] != b"\xd9\x01\x02"


def test_set_encodes_from_a_set_and_decodes_to_a_list() -> None:
    """A Python set is sent as a set and comes back as a list.

    Deliberately asymmetric. SurrealDB's set holds any value - `set<object>`
    is an ordinary column - while a Python set takes only hashable members, so
    decoding into one raised `unhashable type: 'dict'` and lost the whole
    response. A list is also what SurrealDB 2.x and the server's JSON endpoint
    return for a set.
    """
    decoded = cbor.decode(cbor.encode({1, 2, 3}))
    assert isinstance(decoded, list)
    assert sorted(decoded) == [1, 2, 3]


def test_frozenset_encodes_via_the_set_tag() -> None:
    """A frozenset encodes via the set tag and decodes to a list."""
    encoded = cbor.encode(frozenset({4, 5, 6}))
    assert encoded[:2] == b"\xd8\x38"
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, list)
    assert sorted(decoded) == [4, 5, 6]


def test_nested_set_roundtrip() -> None:
    """Sets nested inside containers also use the set tag."""
    decoded = cbor.decode(cbor.encode({"nums": {7, 8, 9}}))
    assert isinstance(decoded["nums"], list)
    assert sorted(decoded["nums"]) == [7, 8, 9]


def test_a_set_of_unhashable_values_decodes() -> None:
    """The defect: a `set<object>` could not be read at all.

    `set(...)` on the decoded members raised `unhashable type: 'dict'`, which
    `decode_response` turned into an `UnexpectedResponseError` covering the
    whole reply - so any `SELECT *` touching such a field failed, and the row
    was unreadable in its native form.
    """
    raw = dumps(CBORTag(constants.TAG_SET, [{"k": "a"}, {"k": "b"}]))
    assert cbor.decode(raw) == [{"k": "a"}, {"k": "b"}]

    raw = dumps(CBORTag(constants.TAG_SET, [[1, 2], [3, 4]]))
    assert cbor.decode(raw) == [[1, 2], [3, 4]]


def test_none_encodes_as_the_none_tag() -> None:
    """``None`` means SurrealDB's NONE: tag 6, 0xc6 0xf6."""
    assert cbor.encode(None) == b"\xc6\xf6"
    assert cbor.decode(cbor.encode(None)) is None


def test_null_encodes_as_plain_cbor_null() -> None:
    """``Null`` means SurrealDB's NULL: plain CBOR null, 0xf6."""
    assert cbor.encode(Null) == b"\xf6"
    assert cbor.decode(cbor.encode(Null)) is Null


def test_null_and_none_stay_distinct_through_a_round_trip() -> None:
    """The whole point: the two must not collapse into each other.

    They did, and it cost data - a NULL field read as ``None`` went back as
    NONE, which deletes the field rather than nulling it.
    """
    payload = {"a": Null, "b": None, "c": [Null, None], "d": {"e": Null}}
    assert cbor.decode(cbor.encode(payload)) == payload


def test_the_generic_cbor_package_still_decodes_null_as_none() -> None:
    """``surrealdb.cbor`` is a general-purpose CBOR codec and stays standard.

    Only the SurrealDB layer knows that a null on its wire means NULL; a
    caller using the re-exported cbor2 API must still get plain ``None``.
    """
    assert loads(b"\xf6") is None
    assert loads(dumps(None)) is None


def test_decimal_still_encodes_as_tag_10() -> None:
    """Finite Decimals are encoded natively as tag 10 (0xca prefix)."""
    encoded = cbor.encode(decimal.Decimal("1.5"))
    assert encoded[0] == 0xCA
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, decimal.Decimal)
    assert decoded == decimal.Decimal("1.5")


def test_uuid_roundtrip_via_native_tag() -> None:
    """UUIDs round-trip using the native cbor tag 37 (unchanged behaviour)."""
    original = uuid.uuid4()
    decoded = cbor.decode(cbor.encode(original))
    assert decoded == original


def test_uuid_tag_9_defensive_decode() -> None:
    """A hand-built string-tagged UUID (tag 9) is decoded defensively."""
    original = uuid.uuid4()
    raw = dumps(CBORTag(constants.TAG_UUID_STRING, str(original)))
    decoded = cbor.decode(raw)
    assert isinstance(decoded, uuid.UUID)
    assert decoded == original
