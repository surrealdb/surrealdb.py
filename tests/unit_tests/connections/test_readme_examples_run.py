"""The README's runnable example blocks are run, not just read.

``test_examples_use_the_real_api`` checks that ``examples/`` names methods that
exist, which catches a renamed API but nothing about whether the code *works*.
Two README blocks were wrong in ways only running them shows:

* the ``into=`` block declared a two-field ``Person`` and then wrote a third
  field to the table, so the very next line raised;
* the sync block's last statement was ``db.query("DELETE temp_data;")`` against
  a table nothing had created, which is a ``NotFoundError`` on 3.x.

These reproduce the blocks statement by statement rather than ``exec``-ing the
markdown: the blocks are fragments with no imports and top-level ``await``, so
extracting and running them literally is not possible, and a paraphrase that
drifted from the README would be worse than no test. Each statement below is
the README's, in the README's order, so a change to one without the other shows
up as a diff a reviewer can see.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from surrealdb import AsyncSurreal, Surreal
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.errors import NotFoundError


@dataclass
class Person:
    """The README's model, verbatim."""

    id: RecordID
    name: str


@pytest.fixture
def person_table(blocking_ws_connection: Any) -> str:
    blocking_ws_connection.query("DELETE person;").execute()
    return "person"


# --------------------------------------------------------------- the into= block


async def test_the_into_block_runs(async_ws_connection: Any, person_table: str) -> None:
    db = async_ws_connection

    person = await db.select(RecordID("person", "tobie"), into=Person)
    assert person is None

    people = await db.select(Table("person"), into=Person)
    assert people == []

    created = await db.create(
        RecordID("person", "tobie"), {"name": "Tobie"}, into=Person
    )
    assert isinstance(created, Person)

    updated = await db.update(Table("person"), {"name": "Updated"}, into=Person)
    assert isinstance(updated, list)
    assert all(isinstance(row, Person) for row in updated)

    inserted = await db.insert(Table("person"), [{"name": "A"}], into=Person)
    assert isinstance(inserted, list)
    assert all(isinstance(row, Person) for row in inserted)

    p = await db.create(RecordID("person", "jaime"), into=Person).merge(
        {"name": "Jaime"}
    )
    assert isinstance(p, Person)

    rows = await db.query("SELECT * FROM person").into(Person, rows=True)
    assert all(isinstance(row, Person) for row in rows)


def test_the_sync_into_block_runs(
    blocking_ws_connection: Any, person_table: str
) -> None:
    db = blocking_ws_connection

    assert db.select(RecordID("person", "tobie"), into=Person) is None
    created = db.create(RecordID("person", "tobie"), {"name": "Tobie"}, into=Person)
    assert isinstance(created, Person)
    rows = db.query("SELECT * FROM person").into(Person, rows=True)
    assert all(isinstance(row, Person) for row in rows)


def test_the_documented_mismatch_message_is_what_the_readme_shows(
    blocking_ws_connection: Any, person_table: str
) -> None:
    """The README quotes this error; it has to be the one that comes out."""
    db = blocking_ws_connection
    db.create(RecordID("person", "tobie"), {"name": "Tobie"})

    with pytest.raises(Exception) as caught:
        db.update(Table("person"), {"active": True}, into=Person)

    message = str(caught.value)
    assert "into=Person could not be built from this record" in message
    assert "unexpected keyword argument 'active'" in message
    assert "Person accepts ['id', 'name']" in message


# --------------------------------------------------------------- the sync block


def test_the_sync_usage_block_runs(connection_params: dict[str, Any]) -> None:
    """The README's ``with Surreal(...)`` block, line for line."""
    with Surreal(connection_params["ws_url"]) as db:
        db.signin({"username": "root", "password": "root"})
        db.use(connection_params["namespace"], connection_params["database_name"])
        db.query("DELETE person;").execute()

        tobie = db.create(RecordID("person", "tobie"), {"name": "Tobie"})
        assert tobie["name"] == "Tobie"

        out = db.create(RecordID("person", "alice")).merge({"name": "Alice"})
        assert out["name"] == "Alice"

        empty = db.create(RecordID("person", "bob")).execute()
        assert empty["id"] == RecordID("person", "bob")

        row = db.select(RecordID("person", "tobie"))
        assert row is not None
        db.delete(RecordID("person", "bob"))

        db.query("DELETE person;").execute()


def test_delete_on_a_missing_table_is_documented_accurately(
    blocking_ws_connection: Any,
) -> None:
    """The README says 3.x raises here and 2.x does not, so check the claim
    against whichever server is actually running."""
    missing = f"absent_{uuid.uuid4().hex[:8]}"
    version = blocking_ws_connection.version()
    major = int(version.replace("surrealdb-", "").split(".")[0])

    if major >= 3:
        with pytest.raises(NotFoundError):
            blocking_ws_connection.query(f"DELETE {missing};").execute()
    else:
        assert blocking_ws_connection.query(f"DELETE {missing};").execute() == [[]]

    # The version-independent spelling the README recommends instead.
    assert (
        blocking_ws_connection.query(f"REMOVE TABLE IF EXISTS {missing};").execute()
        is not None
    )


# --------------------------------------------------------------- the async block


async def test_the_async_usage_block_runs(connection_params: dict[str, Any]) -> None:
    async with AsyncSurreal(connection_params["ws_url"]) as db:
        await db.signin({"username": "root", "password": "root"})
        await db.use(connection_params["namespace"], connection_params["database_name"])
        assert await db.query("RETURN 1").first() == 1


def test_the_files_block_runs(
    blocking_ws_connection: BlockingWsSurrealConnection, tmp_path: Any
) -> None:
    """The README's Files block, statement by statement, in its order.

    It was not covered when file support landed - this harness reproduces blocks
    by hand rather than exec-ing the markdown, so a new block is only covered
    once someone adds it. The block shipped using ``png_bytes`` on the line
    *before* it was assigned, which is a ``NameError`` for anyone who pastes it.
    """
    from surrealdb import File

    bucket = f"readme_{uuid.uuid4().hex[:8]}"
    try:
        blocking_ws_connection.query(
            f'DEFINE BUCKET IF NOT EXISTS {bucket} BACKEND "memory"'
        ).execute()
    except Exception:
        pytest.skip("server has no bucket support")

    source = tmp_path / "avatar.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"pixels")

    # from surrealdb import File, Surreal  -- the connection is the fixture
    avatar = File(bucket, "/photos/avatar.png")

    with source.open("rb") as handle:
        blocking_ws_connection.files.put(avatar, handle.read())

    png_bytes = blocking_ws_connection.files.get(avatar)
    assert png_bytes == source.read_bytes()

    meta = blocking_ws_connection.files.head(avatar)
    assert meta is not None
    assert meta.size == len(png_bytes)
    assert meta.updated is not None

    listed = list(blocking_ws_connection.files.list(bucket, prefix="/photos", limit=50))
    assert [(entry.file.key, entry.size) for entry in listed] == [
        ("/photos/avatar.png", len(png_bytes))
    ]


def test_the_files_encoding_block_runs(
    blocking_ws_connection: BlockingWsSurrealConnection, tmp_path: Any
) -> None:
    """The two-line block under "Why files are bound, not written into queries"."""
    from surrealdb import File

    bucket = f"readme_{uuid.uuid4().hex[:8]}"
    try:
        blocking_ws_connection.query(
            f'DEFINE BUCKET IF NOT EXISTS {bucket} BACKEND "memory"'
        ).execute()
    except Exception:
        pytest.skip("server has no bucket support")

    readme, photo = File(bucket, "/readme.txt"), File(bucket, "/photo.bin")
    source = tmp_path / "photo.bin"
    source.write_bytes(b"binary")

    blocking_ws_connection.files.put(readme, b"hello")
    with source.open("rb") as handle:
        blocking_ws_connection.files.put(photo, handle.read())

    assert blocking_ws_connection.files.get(readme) == b"hello"
    assert blocking_ws_connection.files.get(photo) == b"binary"
