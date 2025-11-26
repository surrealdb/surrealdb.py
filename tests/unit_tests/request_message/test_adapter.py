import os
from typing import Any

import pytest

from surrealdb.request_message.sql_adapter import SqlAdapter

EXPECTED_SQL = (
    "CREATE user:tobie SET name = 'Tobie'; CREATE user:jaime SET name = 'Jaime';"
)


def test_sql_adapter_from_docstring() -> None:
    query = """
    CREATE user:tobie SET name = 'Tobie';
    CREATE user:jaime SET name = 'Jaime';
    """
    sql = SqlAdapter.from_docstring(query)
    assert EXPECTED_SQL == sql
    query = """


            CREATE user:tobie SET name = 'Tobie';

            CREATE 
            user:jaime 
            SET name = 'Jaime';


            """
    sql = SqlAdapter.from_docstring(query)
    assert EXPECTED_SQL == sql


def test_sql_adapter_from_list() -> None:
    query = [
        "CREATE user:tobie SET name = 'Tobie';",
        "",
        "CREATE user:jaime SET name = 'Jaime'",
    ]
    sql = SqlAdapter.from_list(query)
    assert EXPECTED_SQL == sql


def test_sql_adapter_from_file() -> None:
    current_file_path = os.path.abspath(__file__)
    directory = os.path.dirname(current_file_path)
    file_path = os.path.join(directory, "test.sql")
    sql = SqlAdapter.from_file(str(file_path))
    expected_sql = (
        ""
        "CREATE user:tobie SET name = 'Tobie'; "
        "CREATE user:jaime SET name = 'Jaime'; "
        "CREATE user:three SET name = 'Three';"
    )
    assert expected_sql == sql
