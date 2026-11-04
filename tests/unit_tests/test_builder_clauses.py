"""The SurrealQL the CRUD builders render for where(), output() and fetch().

Rendered without a server: these are about the statement text, which is the
one place a condition or a field name is written into the query.
"""

import pytest

from surrealdb.connections.builders import _CrudState
from surrealdb.data.types.table import Table


def _statement(operation: str) -> _CrudState:
    return _CrudState(operation, Table("person"), operation.lower(), False)


def test_a_comment_in_where_cannot_swallow_the_clauses_after_it() -> None:
    builder = _statement("SELECT").where("age > 1 -- adults").limit(10)
    sql, _ = builder._build()
    assert sql.endswith("WHERE (age > 1 -- adults\n) LIMIT 10")


def test_a_second_statement_in_where_stays_inside_the_condition() -> None:
    sql, _ = _statement("DELETE").where("true; DELETE secret")._build()
    assert "WHERE (true; DELETE secret\n)" in sql


def test_output_fields_named_after_keywords_stay_fields() -> None:
    builder = _statement("UPDATE").output(["before", "value", "none", "name"])
    sql, _ = builder._build()
    assert sql.endswith("RETURN ⟨before⟩, ⟨value⟩, ⟨none⟩, ⟨name⟩")


def test_output_and_fetch_delimit_each_segment_of_a_path() -> None:
    sql, _ = _statement("UPDATE").output(["author.name"])._build()
    assert sql.endswith("RETURN ⟨author⟩.⟨name⟩")
    sql, _ = _statement("SELECT").fetch("author", "author.friends")._build()
    assert sql.endswith("FETCH ⟨author⟩, ⟨author⟩.⟨friends⟩")


@pytest.mark.parametrize("path", ["author\n", "first-name", "author.", "*"])
def test_output_and_fetch_refuse_anything_but_a_plain_field_path(path: str) -> None:
    with pytest.raises(ValueError, match="field paths"):
        _statement("SELECT").fetch(path)
    with pytest.raises(ValueError, match="field paths"):
        _statement("UPDATE").output([path])
