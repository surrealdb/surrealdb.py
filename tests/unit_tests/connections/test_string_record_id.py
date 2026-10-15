"""`StringRecordId`: a record id the server parses, and the deprecation of
plain "table:id" strings, which the SDK parses itself."""

import uuid
import warnings
from collections.abc import Iterator
from typing import Any

import pytest

from surrealdb import AsyncSurreal, RecordID, StringRecordId, Surreal
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.cbor import decode, encode
from surrealdb.errors import InvalidRecordIdError

Blocking = BlockingWsSurrealConnection | BlockingHttpSurrealConnection


@pytest.fixture(params=["ws", "http"])
def db(
    request: pytest.FixtureRequest, connection_params: dict[str, Any]
) -> Iterator[Blocking]:
    url = connection_params["ws_url" if request.param == "ws" else "url"]
    connection = Surreal(url)
    connection.signin(connection_params["vars_params"])
    database = f"srid_{uuid.uuid4().hex[:8]}"
    connection.use(connection_params["namespace"], database)
    connection.query(
        "CREATE person:⟨a:b⟩ SET n = 1; CREATE person:1 SET n = 2;"
    ).execute()
    try:
        yield connection
    finally:
        connection.query(f"REMOVE DATABASE IF EXISTS {database};").execute()
        connection.close()


def test_the_server_parses_ids_the_sdk_cannot(db: Blocking) -> None:
    complex_id = StringRecordId("person:⟨a:b⟩")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert db.select(complex_id).execute() == {
            "id": RecordID("person", "a:b"),
            "n": 1,
        }
        updated: Any = db.update(StringRecordId("person:1")).merge({"m": 3})
        assert updated["m"] == 3
        assert db.delete(complex_id).execute() == {
            "id": RecordID("person", "a:b"),
            "n": 1,
        }
        assert (
            db.query("RETURN $id.n;", {"id": StringRecordId("person:1")}).first() == 2
        )


def test_a_plain_string_still_works_but_is_deprecated(db: Blocking) -> None:
    with pytest.warns(
        DeprecationWarning, match=r"StringRecordId\('person:1'\)"
    ) as caught:
        record: Any = db.select("person:1").execute()
    assert record["n"] == 2
    assert caught[0].filename == __file__


def test_a_table_name_is_not_deprecated(db: Blocking) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rows: Any = db.select("person").execute()
        assert len(rows) == 2


async def test_async(connection_params: dict[str, Any]) -> None:
    db = AsyncSurreal(connection_params["ws_url"])
    await db.signin(connection_params["vars_params"])
    await db.use(connection_params["namespace"], connection_params["database_name"])
    try:
        await db.query("UPSERT srid_async:⟨x-y⟩ SET n = 5;")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            record: Any = await db.select(StringRecordId("srid_async:⟨x-y⟩"))
        assert record["n"] == 5
    finally:
        await db.query("REMOVE TABLE IF EXISTS srid_async;")
        await db.close()


def test_encoded_as_a_record_id_tag_holding_the_string() -> None:
    encoded = encode(StringRecordId("person:⟨a:b⟩"))
    assert encoded[:1] == b"\xc8"
    assert decode(encoded[1:]) == "person:⟨a:b⟩"


def test_value_semantics() -> None:
    a = StringRecordId("person:1")
    assert a == StringRecordId("person:1")
    assert a != StringRecordId("person:2")
    assert a != "person:1"
    assert hash(a) == hash(StringRecordId("person:1"))
    assert str(a) == "person:1"
    assert repr(a) == "StringRecordId('person:1')"
    with pytest.raises(TypeError):
        StringRecordId(1)  # type: ignore[arg-type]
    with pytest.raises(InvalidRecordIdError):
        StringRecordId("person")
