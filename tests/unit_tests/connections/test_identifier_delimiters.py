"""Identifiers containing a backslash or ``⟩`` survive the round trip.

``escape_identifier`` wrapped everything in ``⟨...⟩`` and escaped ``⟩`` as
``\\⟩``, on the stated assumption that ``⟨...⟩`` accepts any string on every
supported version. It does not, and the failures were not symmetric - each of
these was produced by the old code and refused by a live server:

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

These run against whichever server the suite is pointed at, so the version split
above is recorded here rather than asserted - what is asserted is that every
name comes back as itself, which has to hold on both.
"""

import pytest

from surrealdb import RecordID, escape_identifier
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

# Names that need a delimiter. The first group was already fine and must keep
# its exact previous rendering; the second group is what used to break.
ALREADY_WORKED = [
    pytest.param("a b", id="space"),
    pytest.param("héllo", id="accent"),
    pytest.param("emoji\U0001f389", id="emoji"),
    pytest.param("tick`mark", id="backtick"),
    pytest.param("open⟨angle", id="opening-angle"),
    pytest.param("1tbl", id="leading-digit"),
    pytest.param("__", id="no-letters"),
]
USED_TO_BREAK = [
    pytest.param("with⟩angle", id="closing-angle"),
    pytest.param("back\\slash", id="backslash"),
    pytest.param("trailing\\", id="trailing-backslash"),
    pytest.param("tick`and⟩angle", id="backtick-and-angle"),
    pytest.param("a\\\\b", id="double-backslash"),
    pytest.param("\\", id="only-a-backslash"),
]


@pytest.mark.parametrize("name", ALREADY_WORKED + USED_TO_BREAK)
def test_a_delimited_name_reads_back_as_itself_as_a_field(
    blocking_ws_connection: BlockingWsSurrealConnection, name: str
) -> None:
    rendered = escape_identifier(name)

    row = blocking_ws_connection.query(f"RETURN {{ {rendered}: 1 }}").first()

    assert isinstance(row, dict)
    assert next(iter(row)) == name


@pytest.mark.parametrize("name", ALREADY_WORKED + USED_TO_BREAK)
def test_a_record_id_renders_and_parses_back(
    blocking_ws_connection: BlockingWsSurrealConnection, name: str
) -> None:
    """``RecordID.__str__`` goes through the same escaping, on both halves."""
    record = RecordID(name, name)

    parsed = blocking_ws_connection.query(f"RETURN {record}").first()

    assert isinstance(parsed, RecordID)
    assert parsed.table_name == name
    assert parsed.id == name


@pytest.mark.parametrize("name", ALREADY_WORKED)
def test_names_that_worked_keep_their_previous_rendering(name: str) -> None:
    """The fix must not churn output for names that were never broken.

    Anything already round-tripping stays in ``⟨...⟩`` - only a name holding a
    backslash or ``⟩`` moves to backticks.
    """
    assert escape_identifier(name) == f"⟨{name}⟩"


@pytest.mark.parametrize("name", USED_TO_BREAK)
def test_names_that_broke_are_delimited_with_backticks(name: str) -> None:
    rendered = escape_identifier(name)

    assert rendered.startswith("`")
    assert rendered.endswith("`")


def test_a_backslash_is_doubled_rather_than_left_to_escape_the_delimiter() -> None:
    """The specific mechanic behind the trailing-backslash failure."""
    assert escape_identifier("trailing\\") == "`trailing\\\\`"
    assert escape_identifier("a\\b") == "`a\\\\b`"


def test_a_backtick_inside_backticks_is_escaped() -> None:
    assert escape_identifier("tick`and⟩angle") == "`tick\\`and⟩angle`"


def test_a_plain_name_is_still_bare() -> None:
    """The common case must not gain delimiters."""
    assert escape_identifier("person") == "person"
    assert escape_identifier("user_name2") == "user_name2"


def test_the_empty_name_is_unchanged() -> None:
    assert escape_identifier("") == "⟨⟩"
