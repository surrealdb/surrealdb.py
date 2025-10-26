"""Tests for BlockingEmbeddedSurrealConnection."""

import pytest

from surrealdb import Surreal


def test_mem_connection() -> None:
    """Test in-memory database connection."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Create a record
        result = db.create("person", {"name": "Alice", "age": 30})
        assert result is not None

        # Select the record
        people = db.select("person")
        assert people is not None


def test_create_and_select() -> None:
    """Test basic create and select operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Create
        created = db.create("user", {"name": "Bob", "email": "bob@example.com"})
        assert created is not None

        # Select all
        users = db.select("user")
        assert users is not None


def test_update_operation() -> None:
    """Test update operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Create
        db.create("product", {"name": "Widget", "price": 10})

        # Update
        updated = db.update("product", {"name": "Widget", "price": 15})
        assert updated is not None


def test_delete_operation() -> None:
    """Test delete operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Create
        db.create("temp", {"data": "test"})

        # Delete
        deleted = db.delete("temp")
        assert deleted is not None


def test_query_operation() -> None:
    """Test SurrealQL query execution."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Query
        result = db.query("CREATE person SET name = 'Charlie', age = 25")
        assert result is not None

        # Query with variables
        result = db.query("SELECT * FROM person WHERE age > $min_age", {"min_age": 20})
        assert result is not None


def test_let_and_unset() -> None:
    """Test variable management."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Let
        db.let("name", "David")

        # Use variable in query
        result = db.query("CREATE person SET name = $name")
        assert result is not None

        # Unset
        db.unset("name")


def test_merge_operation() -> None:
    """Test merge operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Create
        db.create("item", {"name": "Item1", "quantity": 5})

        # Merge
        merged = db.merge("item", {"quantity": 10})
        assert merged is not None


def test_upsert_operation() -> None:
    """Test upsert operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Upsert (insert)
        upserted = db.upsert("record:1", {"value": "first"})
        assert upserted is not None

        # Upsert (update)
        upserted = db.upsert("record:1", {"value": "second"})
        assert upserted is not None


def test_insert_operation() -> None:
    """Test insert operations."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Insert single
        inserted = db.insert("entry", {"data": "test"})
        assert inserted is not None

        # Insert multiple
        inserted = db.insert("entry", [{"data": "test1"}, {"data": "test2"}])
        assert inserted is not None


def test_connection_lifecycle() -> None:
    """Test connection lifecycle management."""
    db = Surreal("mem://")

    # Connect
    db.connect("mem://")
    db.use("test", "test")

    # Use
    db.create("test", {"value": 1})

    # Close
    db.close()


def test_invalidate() -> None:
    """Test session invalidation."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        # Invalidate session
        db.invalidate()
