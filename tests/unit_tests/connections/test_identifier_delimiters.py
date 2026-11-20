"""Delimited identifiers use backticks and survive the round trip.

``escape_identifier`` used to wrap names in ``⟨...⟩`` and escape ``⟩`` as
``\\⟩``, on the stated assumption that ``⟨...⟩`` accepts any string on every
supported version. It does not, and the failures were not symmetric - each of
these was produced by that code and refused by a live server:

===========================  ==========================  =======================
emitted                      2.3.10                      3.2.3
===========================  ==========================  =======================
``⟨with\\⟩angle⟩``             accepted                    Invalid escape sequence
``⟨back\\slash⟩``              internal error              Invalid escape sequence
``⟨trailing\\⟩``               internal error              Unexpected end of file
===========================  ==========================  =======================

The trailing-backslash case is the one to keep in mind: the backslash escapes
the closing delimiter, so the identifier never ends and consumes whatever came
after it in the statement.

Every delimited name now uses backticks, with ``\\`` and ``` ` ``` escaped by a
backslash. That is read identically by 2.0.5 through 4.0.0, and it is what the
server itself displays from 2.6.0 on (issue #427), so ``str(RecordID(...))``
matches Surrealist, the CLI and the other SDKs.

These run against whichever server the suite is pointed at, so the version split
above is recorded here rather than asserted - what is asserted is that every
name comes back as itself, which has to hold on all of them.
"""

import pytest

from surrealdb import RecordID, Table, escape_identifier
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

NEEDS_NO_ESCAPE = [
    pytest.param("a b", id="space"),
    pytest.param("héllo", id="accent"),
    pytest.param("emoji\U0001f389", id="emoji"),
    pytest.param("open⟨angle", id="opening-angle"),
    pytest.param("with⟩angle", id="closing-angle"),
    pytest.param("⟨both⟩", id="both-angles"),
    pytest.param("1tbl", id="leading-digit"),
    pytest.param("__", id="no-letters"),
    pytest.param("123", id="all-digits"),
    pytest.param("a:b", id="colon"),
    pytest.param("a..b", id="range-dots"),
    pytest.param("line\nbreak", id="newline"),
]
NEEDS_ESCAPE = [
    pytest.param("tick`mark", id="backtick"),
    pytest.param("back\\slash", id="backslash"),
    pytest.param("trailing\\", id="trailing-backslash"),
    pytest.param("tick`and⟩angle", id="backtick-and-angle"),
    pytest.param("a\\\\b", id="double-backslash"),
    pytest.param("\\", id="only-a-backslash"),
    pytest.param("`", id="only-a-backtick"),
    pytest.param("\\`", id="backslash-then-backtick"),
]


@pytest.mark.parametrize("name", NEEDS_NO_ESCAPE + NEEDS_ESCAPE)
def test_a_delimited_name_reads_back_as_itself_as_a_field(
    blocking_ws_connection: BlockingWsSurrealConnection, name: str
) -> None:
    rendered = escape_identifier(name)

    row = blocking_ws_connection.query(f"RETURN {{ {rendered}: 1 }}").first()

    assert isinstance(row, dict)
    assert next(iter(row)) == name


@pytest.mark.parametrize("name", NEEDS_NO_ESCAPE + NEEDS_ESCAPE)
def test_a_record_id_renders_and_parses_back(
    blocking_ws_connection: BlockingWsSurrealConnection, name: str
) -> None:
    """``RecordID.__str__`` goes through the same escaping, on both halves."""
    record = RecordID(name, name)

    parsed = blocking_ws_connection.query(f"RETURN {record}").first()

    assert isinstance(parsed, RecordID)
    assert parsed.table_name == name
    assert parsed.id == name


KEYS = [
    pytest.param("8pkgf59qqokxbqjtured", id="generated-id-with-leading-digit"),
    pytest.param("1abc", id="leading-digit"),
    pytest.param("1e10", id="exponent-lookalike"),
    pytest.param("8d", id="duration-lookalike"),
    pytest.param("1_a", id="digit-underscore-letter"),
    pytest.param("_1", id="underscore-digit"),
    pytest.param("1_000", id="digits-underscore"),
    pytest.param("NaN", id="nan"),
    pytest.param("Infinity", id="infinity"),
    pytest.param("select", id="keyword"),
]
# What 2.0.5 shows instead of what this SDK renders. It wraps in ⟨⟩, and it
# shows NaN and Infinity bare, which it then cannot read back - the SDK's
# backticked form is what 2.0.5 parses.
SHOWN_BY_2_0 = {
    "_1": "t:⟨_1⟩",
    "1_000": "t:⟨1_000⟩",
    "NaN": "t:NaN",
    "Infinity": "t:Infinity",
}


@pytest.mark.parametrize("key", KEYS)
def test_a_record_id_key_renders_as_the_server_displays_it(
    blocking_ws_connection: BlockingWsSurrealConnection, key: str
) -> None:
    """Issue #448: the key half follows the server's key rule, not the table rule.

    A key may start with a digit, which a table name may not, so a generated id
    such as ``8pkgf59qqokxbqjtured`` is shown bare by the server and must be by
    ``str()`` too. ``NaN`` and ``Infinity`` are the opposite case: bare, the
    parser reads them as numbers.
    """
    record = RecordID("t", key)

    parsed = blocking_ws_connection.query(f"RETURN {record}").first()
    shown = blocking_ws_connection.query(
        "RETURN <string> $record", {"record": record}
    ).first()

    assert parsed == record
    assert shown in (str(record), SHOWN_BY_2_0.get(key))


def test_generated_ids_render_as_the_server_displays_them(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Issue #448: insert in a loop and print each new id.

    About a quarter of generated ids start with a digit, and those came out
    wrapped while the rest were bare.
    """
    for index in range(40):
        record = blocking_ws_connection.insert(Table("issue_448"), {"index": index})
        assert isinstance(record, list)
        record_id = record[0]["id"]
        assert isinstance(record_id, RecordID)

        shown = blocking_ws_connection.query(
            "RETURN <string> $record", {"record": record_id}
        ).first()

        assert str(record_id) == shown


def test_the_empty_id_reads_back_as_itself(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    parsed = blocking_ws_connection.query(f"RETURN {RecordID('t', '')}").first()

    assert parsed == RecordID("t", "")


@pytest.mark.parametrize("name", NEEDS_NO_ESCAPE)
def test_a_name_is_wrapped_in_backticks_verbatim(name: str) -> None:
    """Nothing but ``\\`` and ``` ` ``` needs escaping inside backticks."""
    assert escape_identifier(name) == f"`{name}`"


@pytest.mark.parametrize("name", NEEDS_NO_ESCAPE + NEEDS_ESCAPE)
def test_no_name_is_delimited_with_angle_brackets(name: str) -> None:
    rendered = escape_identifier(name)

    assert rendered.startswith("`")
    assert rendered.endswith("`")


def test_a_backslash_is_doubled_rather_than_left_to_escape_the_delimiter() -> None:
    """The specific mechanic behind the trailing-backslash failure."""
    assert escape_identifier("trailing\\") == "`trailing\\\\`"
    assert escape_identifier("a\\b") == "`a\\\\b`"


def test_a_backtick_inside_backticks_is_escaped() -> None:
    assert escape_identifier("tick`mark") == "`tick\\`mark`"
    assert escape_identifier("tick`and⟩angle") == "`tick\\`and⟩angle`"


def test_a_backslash_is_escaped_before_a_backtick() -> None:
    """Doing it the other way round would double the backtick's own escape."""
    assert escape_identifier("\\`") == "`\\\\\\``"


def test_a_plain_name_is_still_bare() -> None:
    """The common case must not gain delimiters."""
    assert escape_identifier("person") == "person"
    assert escape_identifier("user_name2") == "user_name2"


def test_the_empty_name_is_an_empty_pair_of_backticks() -> None:
    assert escape_identifier("") == "``"
