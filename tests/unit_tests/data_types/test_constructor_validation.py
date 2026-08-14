"""``RecordID`` and ``Table`` refuse arguments SurrealDB cannot use.

Both constructors used to accept anything at all, and the two halves failed
very differently.

``Table`` was a data bug, not a message one. ``Table(None)`` reached the server
as the *table named* ``None`` and the write succeeded: ``insert(Table(None),
[row])`` returned a plausible-looking record, ``SELECT * FROM ⟨None⟩`` found it,
and ``INFO FOR DB`` listed a table called ``None`` - on 2.x and 3.x alike. The
row was really written, just nowhere any query against the intended table would
look. ``Table(123)`` died inside ``escape_identifier`` with ``TypeError: 'int'
object is not iterable``, naming neither argument nor mistake.

``RecordID`` was the message half: every bad id encoded cleanly and came back
from the server as ``ValidationError: Parse error``, which names nothing, for a
mistake decidable before any I/O.

The accept set is empirical, not from the documentation - each type below was
created server-side and read back on live 2.0.5 and 3.2.3 servers. ``tuple`` is
in it for that reason: it round-trips today, so rejecting it would have broken
composite-key users silently.
"""

import uuid
from typing import Any

import pytest

from surrealdb.data.types.range import BoundIncluded, Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.set import SurrealSet
from surrealdb.data.types.table import Table

# --------------------------------------------------------------- what is legal


@pytest.mark.parametrize(
    "identifier",
    [
        pytest.param("abc", id="str"),
        pytest.param("", id="empty-str"),
        pytest.param("has space", id="str-with-space"),
        pytest.param("héllo→", id="unicode-str"),
        pytest.param(1, id="int"),
        pytest.param(-5, id="negative-int"),
        pytest.param(9223372036854775807, id="i64-max"),
        pytest.param(uuid.uuid4(), id="uuid"),
        pytest.param(["a", 1], id="list"),
        pytest.param(("a", 1), id="tuple"),
        pytest.param({"a": 1}, id="dict"),
        pytest.param([1.5, None, True], id="list-with-inner-floats"),
        pytest.param({"k": 1.5}, id="dict-with-inner-float"),
        pytest.param(Range(BoundIncluded(1), BoundIncluded(3)), id="range"),
    ],
)
def test_every_id_the_server_accepts_is_accepted(identifier: Any) -> None:
    """Including the two that a stricter check would wrongly refuse.

    The allowlist is deliberately *shallow*: a list or dict id is accepted
    whatever it contains, because a recursive check would reject ids that
    demonstrably round-trip - ``["a", 1.5, None]`` comes back with its types
    intact even though a bare ``1.5`` is not a legal id.
    """
    assert RecordID("person", identifier).id == identifier


@pytest.mark.parametrize(
    "name",
    ["person", "", "has space", "héllo", "1tbl", "12345", "a:b"],
)
def test_every_table_name_the_server_accepts_is_accepted(name: str) -> None:
    """Only the type is checked, never the content.

    SurrealDB takes any string as a table name - all of these were created and
    read back on a live server - so there is nothing else to be sure of.
    """
    assert Table(name).table_name == name
    assert RecordID(name, 1).table_name == name


# --------------------------------------------------------------- what is not


@pytest.mark.parametrize(
    ("identifier", "expected_in_message"),
    [
        pytest.param(None, "no NONE record id", id="none"),
        pytest.param(True, "subclass of int", id="bool"),
        pytest.param(1.5, "no float record id", id="float"),
        pytest.param(b"xy", "bytes", id="bytes"),
        pytest.param({1, 2}, "set", id="set"),
        pytest.param(object(), "object", id="object"),
        pytest.param(Table("person"), "Table", id="table"),
    ],
)
def test_an_id_the_server_refuses_is_refused_here(
    identifier: Any, expected_in_message: str
) -> None:
    with pytest.raises(TypeError) as caught:
        RecordID("person", identifier)

    message = str(caught.value)
    assert "RecordID() id must be one of" in message
    assert expected_in_message in message
    # The value itself, so the caller can see which one of several it was.
    assert repr(identifier) in message


def test_bool_is_refused_despite_being_an_int() -> None:
    """``isinstance(True, int)`` is ``True``, so a plain allowlist check lets
    every boolean through to the server that refuses it."""
    assert isinstance(True, int)

    with pytest.raises(TypeError) as caught:
        RecordID("person", True)

    assert "bool" in str(caught.value)


def test_a_surreal_set_is_refused_despite_being_a_list() -> None:
    """The same trap one layer along: ``SurrealSet`` subclasses ``list``, and a
    set is not a record id on the wire."""
    assert isinstance(SurrealSet([1]), list)

    with pytest.raises(TypeError) as caught:
        RecordID("person", SurrealSet([1]))

    assert "SurrealSet" in str(caught.value) or "set" in str(caught.value)


@pytest.mark.parametrize(
    "name", [None, 123, b"person", 1.5, ["person"], Table("person")]
)
def test_a_non_string_table_name_is_refused(name: Any) -> None:
    with pytest.raises(TypeError) as caught:
        Table(name)
    assert "Table() name must be a str" in str(caught.value)

    with pytest.raises(TypeError) as caught:
        RecordID(name, 1)
    assert "RecordID() table_name must be a str" in str(caught.value)


# --------------------------------------------------------------- the messages


def test_swapped_arguments_are_named_as_such() -> None:
    """``RecordID(1, "x")`` is much more often a swap than a wrong type."""
    with pytest.raises(TypeError) as caught:
        RecordID(1, "x")  # type: ignore[arg-type]

    assert "arguments look swapped" in str(caught.value)
    assert "RecordID('x', 1)" in str(caught.value)


def test_a_table_passed_as_a_name_says_what_to_pass_instead() -> None:
    with pytest.raises(TypeError) as caught:
        Table(Table("person"))  # type: ignore[arg-type]

    assert "table.table_name" in str(caught.value)


def test_none_points_at_server_generated_ids() -> None:
    """Someone passing ``None`` has not made a typo - they have no id yet, and
    need a different call rather than a different value."""
    with pytest.raises(TypeError) as caught:
        RecordID("person", None)

    assert "db.create(Table('person'), data)" in str(caught.value)


def test_the_errors_are_type_errors_not_surreal_errors() -> None:
    """A wrong argument type is a caller mistake, and this SDK raises builtins
    for those - the ``SurrealError`` tree is for operational failures."""
    from surrealdb.errors import SurrealError

    for build in (lambda: RecordID("t", None), lambda: Table(None)):
        with pytest.raises(TypeError) as caught:
            build()
        assert not isinstance(caught.value, SurrealError)


# --------------------------------------------------- the decode path is exempt


def test_the_decoder_accepts_an_id_type_the_constructor_would_refuse() -> None:
    """The constraint the whole design turns on.

    The CBOR decoder builds a ``RecordID`` for every record read back. If it
    validated, a future server's new id type would stop the record being
    *readable* - and because ``tag_decoder`` runs inside the decode of a whole
    frame, it would take every other row with it. A bad write is recoverable; a
    record you cannot load is not.
    """
    from surrealdb.cbor import CBORTag, dumps
    from surrealdb.data import cbor
    from surrealdb.data.types import constants

    # A float id: refused by the constructor, and by the server - but if one
    # ever arrives, it has to decode.
    frame = dumps(CBORTag(constants.TAG_RECORD_ID, ["person", 1.5]))
    decoded = cbor.decode(frame)

    assert isinstance(decoded, RecordID)
    assert decoded.id == 1.5
    assert decoded.table_name == "person"


def test_the_decoder_accepts_a_table_name_the_constructor_would_refuse() -> None:
    from surrealdb.cbor import CBORTag, dumps
    from surrealdb.data import cbor
    from surrealdb.data.types import constants

    decoded = cbor.decode(dumps(CBORTag(constants.TAG_TABLE_NAME, 123)))

    assert isinstance(decoded, Table)
    # Held as `Any`: the attribute is annotated `str`, which is true of every
    # name a server has ever sent and is exactly what `_unchecked` does not
    # promise.
    name: Any = decoded.table_name
    assert name == 123


def test_a_decoded_record_id_re_encodes_unchanged() -> None:
    """Round-tripping a value the constructor would refuse must still work, or
    the exemption above buys a readable record you cannot write back."""
    from surrealdb.cbor import CBORTag, dumps
    from surrealdb.data import cbor
    from surrealdb.data.types import constants

    frame = dumps(CBORTag(constants.TAG_RECORD_ID, ["person", 1.5]))
    decoded = cbor.decode(frame)

    assert cbor.decode(cbor.encode(decoded)) == decoded


@pytest.mark.parametrize("cls", [RecordID, Table])
def test_unchecked_sets_the_same_attributes_as_the_constructor(cls: type) -> None:
    """Two constructors that must stay in step. Compares the instance dict, so
    adding a field to ``__init__`` and forgetting ``_unchecked`` fails here
    rather than as an ``AttributeError`` somewhere downstream.
    """
    if cls is RecordID:
        checked: Any = RecordID("person", 1)
        unchecked: Any = RecordID._unchecked("person", 1)  # pyright: ignore[reportPrivateUsage]
    else:
        checked = Table("person")
        unchecked = Table._unchecked("person")  # pyright: ignore[reportPrivateUsage]

    assert vars(checked).keys() == vars(unchecked).keys()
    assert vars(checked) == vars(unchecked)
    assert checked == unchecked


# --------------------------------------------------------------- neighbours


def test_parse_still_works() -> None:
    """``RecordID.parse`` always yields a string id, so it is unaffected - but
    it goes through the constructor, so it would break if the check were wrong.
    """
    assert RecordID.parse("person:tobie") == RecordID("person", "tobie")
    assert RecordID.parse("person:complex:id").id == "complex:id"


def test_a_bytes_id_from_the_wire_renders_without_decoding() -> None:
    """``__str__``'s bytes branch is live because of ``_unchecked``.

    It used to ``.decode()``, which raised ``UnicodeDecodeError`` on anything
    that was not UTF-8 and - worse - rendered ``b"xy"`` as ``person:xy``, which
    names a *different* record from the one it holds.
    """
    record = RecordID._unchecked("person", b"\xff\xfe")  # pyright: ignore[reportPrivateUsage]

    rendered = str(record)

    assert rendered == "person:b'\\xff\\xfe'"
    assert str(RecordID._unchecked("person", b"xy")) != str(  # pyright: ignore[reportPrivateUsage]
        RecordID("person", "xy")
    )
