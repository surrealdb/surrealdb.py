"""Tests for BlockingEmbeddedSurrealConnection."""

import pytest

from surrealdb import Surreal


def test_mem_connection() -> None:
    """Test in-memory database connection."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        result = db.create("person", {"name": "Alice", "age": 30})
        assert result is not None

        people = db.select("person")
        assert people is not None


def test_create_and_select() -> None:
    """Test basic create and select operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        created = db.create("user", {"name": "Bob", "email": "bob@example.com"})
        assert created is not None

        users = db.select("user")
        assert users is not None


def test_update_operation() -> None:
    """Test update operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        db.create("product", {"name": "Widget", "price": 10})

        updated = db.update("product", {"name": "Widget", "price": 15})
        assert updated is not None


def test_delete_operation() -> None:
    """Test delete operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        db.create("temp", {"data": "test"})

        deleted = db.delete("temp")
        assert deleted is not None


def test_query_operation() -> None:
    """Test SurrealQL query execution."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # query() returns a builder under eager-sync; a terminal (.first() /
        # .execute()) is required to actually run the statement.
        created = db.query("CREATE person SET name = 'Charlie', age = 25").first()
        assert isinstance(created, list)
        assert created[0]["name"] == "Charlie"

        rows = db.query(
            "SELECT * FROM person WHERE age > $min_age", {"min_age": 20}
        ).first()
        assert isinstance(rows, list)
        assert any(row["name"] == "Charlie" for row in rows)


def test_let_and_unset() -> None:
    """Test variable management."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        db.let("name", "David")

        result = db.query("CREATE person SET name = $name")
        assert result is not None

        db.unset("name")


def test_merge_operation() -> None:
    """Test merge operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        db.create("item", {"name": "Item1", "quantity": 5})

        merged = db.update("item").merge({"quantity": 10})
        assert merged is not None


def test_upsert_operation() -> None:
    """Test upsert operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        upserted = db.upsert("record:1", {"value": "first"})
        assert upserted is not None

        upserted = db.upsert("record:1", {"value": "second"})
        assert upserted is not None


def test_insert_operation() -> None:
    """Test insert operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        inserted = db.insert("entry", {"data": "test"})
        assert inserted is not None

        inserted = db.insert("entry", [{"data": "test1"}, {"data": "test2"}])
        assert inserted is not None


def test_connection_lifecycle() -> None:
    """Test connection lifecycle management."""
    db = Surreal("mem://")

    db.connect("mem://")
    db.use("test", "test")

    db.create("test", {"value": 1})

    db.close()


def test_invalidate() -> None:
    """Test session invalidation."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        db.invalidate()
