"""``SurrealSet`` takes a type argument and behaves as it did without one.

The type argument is for type checkers: ``SurrealSet[str]`` and a bare
``SurrealSet`` are the same class at run time, so the decoder, the encoder and
everything that handles one see no difference. The typing is pinned by
``tests/unit_tests/test_surreal_set_typing.py``.
"""

import copy
import pickle

import pytest

from surrealdb import SurrealSet as ExportedSurrealSet
from surrealdb.data import cbor
from surrealdb.data.types.set import SurrealSet

SET_TAG = b"\xd8\x38"


def test_the_exported_name_is_the_class() -> None:
    assert ExportedSurrealSet is SurrealSet


def test_a_bare_set_builds_and_compares_like_a_list() -> None:
    assert SurrealSet() == []
    assert SurrealSet([1, 2]) == [1, 2]
    assert SurrealSet([1, 2])[0] == 1
    assert isinstance(SurrealSet([1]), list)
    assert repr(SurrealSet([1, 2])) == "SurrealSet([1, 2])"


def test_a_subscripted_set_builds_the_same_class() -> None:
    typed = SurrealSet[int]([1, 2])

    assert type(typed) is SurrealSet
    assert typed == SurrealSet([1, 2]) == [1, 2]
    assert repr(typed) == "SurrealSet([1, 2])"
    assert isinstance(typed, SurrealSet)
    assert not hasattr(typed, "__dict__")


def test_an_empty_subscripted_set_is_empty() -> None:
    assert SurrealSet[str]() == []
    assert type(SurrealSet[str]()) is SurrealSet


@pytest.mark.parametrize("make", [SurrealSet, SurrealSet[int]])
def test_both_spellings_encode_under_the_set_tag(make: type[SurrealSet]) -> None:
    encoded = cbor.encode(make([1, 2]))

    assert encoded[:2] == SET_TAG
    assert encoded == cbor.encode(SurrealSet([1, 2]))


def test_decoding_a_set_still_yields_a_surreal_set() -> None:
    decoded = cbor.decode(cbor.encode(SurrealSet[str](["a", "b"])))

    assert type(decoded) is SurrealSet
    assert decoded == ["a", "b"]
    assert cbor.decode(cbor.encode({1, 2})) == [1, 2]


@pytest.mark.parametrize("protocol", range(2, pickle.HIGHEST_PROTOCOL + 1))
def test_a_set_pickles_and_copies(protocol: int) -> None:
    original = SurrealSet[int]([3, 1, 2])

    revived = pickle.loads(pickle.dumps(original, protocol=protocol))

    assert type(revived) is SurrealSet
    assert revived == original
    assert copy.copy(original) == original
    assert type(copy.deepcopy(original)) is SurrealSet
