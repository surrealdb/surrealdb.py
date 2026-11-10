"""``SurrealSet`` carries the element type of a ``set<T>``.

``class SurrealSet(list[Any])`` threw the element type away, so reading
``row["tags"][0]`` was ``Any`` whatever the field held. It is generic now, and
a bare ``SurrealSet`` is still ``SurrealSet[Any]``: the type argument has a
default, so code that never named one gets no new error under strict pyright or
under mypy's ``disallow_any_generics``, and nothing it passed before is refused.

``assert_type`` is a runtime no-op, so this module is a regression guard for the
type checkers, not for the runtime: if the type argument is not carried through,
an element is ``Any`` and ``assert_type`` fails under both, and if the default
is dropped, pyright reports every bare name below as a missing type argument.
mypy only reports that under ``disallow_any_generics``, which the test run
relaxes, so the bare name under mypy is held by the strict run over ``src/``,
where ``Value``, the decoder and the encoder all use it.
"""

import sys
from typing import TYPE_CHECKING, Any

if sys.version_info >= (3, 11):
    from typing import assert_type
else:
    from typing_extensions import assert_type

from surrealdb import SurrealSet as ExportedSurrealSet
from surrealdb.data.types.set import SurrealSet
from surrealdb.types import Value


def bare(tags: SurrealSet) -> SurrealSet:
    return tags


def test_an_element_keeps_its_type() -> None:
    if not TYPE_CHECKING:
        return
    tags: SurrealSet[str] = SurrealSet(["a", "b"])

    assert_type(tags, SurrealSet[str])
    assert_type(tags[0], str)
    assert_type(tags[:1], list[str])
    for tag in tags:
        assert_type(tag, str)
    assert_type(list(tags), list[str])
    assert_type(SurrealSet([1, 2]), SurrealSet[int])
    assert_type(SurrealSet[int]([1, 2]), SurrealSet[int])
    assert_type(ExportedSurrealSet[bytes]([b"a"])[0], bytes)


def test_a_bare_set_is_any() -> None:
    if not TYPE_CHECKING:
        return
    anything: SurrealSet = SurrealSet([1, "a"])

    assert_type(anything, SurrealSet[Any])
    assert_type(anything[0], Any)
    assert_type(bare(SurrealSet(["a"])), SurrealSet[Any])


def test_typed_and_bare_sets_convert_either_way() -> None:
    if not TYPE_CHECKING:
        return
    typed: SurrealSet[str] = SurrealSet(["a"])
    anything: SurrealSet = typed
    back: SurrealSet[int] = anything

    assert_type(back, SurrealSet[int])


def test_a_set_is_still_a_value() -> None:
    if not TYPE_CHECKING:
        return
    ints = SurrealSet([1, 2])
    strings: SurrealSet[str] = SurrealSet(["a"])
    value: Value = ints
    row: dict[str, Value] = {"ints": ints, "strings": strings}
    as_list: list[str] = strings

    assert as_list is strings
    assert value is ints
    assert row["ints"] is ints
