"""Tests for AsyncEmbeddedSurrealConnection."""

import pytest

from surrealdb import AsyncSurreal


@pytest.mark.asyncio
async def test_mem_connection() -> None:
    """Test in-memory database connection."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Create a record
        result = await db.create("person", {"name": "Alice", "age": 30})
        assert result is not None

        # Select the record
        people = await db.select("person")
        assert people is not None


@pytest.mark.asyncio
async def test_create_and_select() -> None:
    """Test basic create and select operations."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Create
        created = await db.create("user", {"name": "Bob", "email": "bob@example.com"})
        assert created is not None

        # Select all
        users = await db.select("user")
        assert users is not None


@pytest.mark.asyncio
async def test_update_operation() -> None:
    """Test update operations."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Create
        await db.create("product", {"name": "Widget", "price": 10})

        # Update
        updated = await db.update("product", {"name": "Widget", "price": 15})
        assert updated is not None


@pytest.mark.asyncio
async def test_delete_operation() -> None:
    """Test delete operations."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Create
        await db.create("temp", {"data": "test"})

        # Delete
        deleted = await db.delete("temp")
        assert deleted is not None


@pytest.mark.asyncio
async def test_query_operation() -> None:
    """Test SurrealQL query execution."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Query
        result = await db.query("CREATE person SET name = 'Charlie', age = 25")
        assert result is not None

        # Query with variables
        result = await db.query(
            "SELECT * FROM person WHERE age > $min_age", {"min_age": 20}
        )
        assert result is not None


@pytest.mark.asyncio
async def test_let_and_unset() -> None:
    """Test variable management."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Let
        await db.let("name", "David")

        # Use variable in query
        result = await db.query("CREATE person SET name = $name")
        assert result is not None

        # Unset
        await db.unset("name")


@pytest.mark.asyncio
async def test_merge_operation() -> None:
    """Test merge operations."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Create
        await db.create("item", {"name": "Item1", "quantity": 5})

        # Merge
        merged = await db.merge("item", {"quantity": 10})
        assert merged is not None


@pytest.mark.asyncio
async def test_upsert_operation() -> None:
    """Test upsert operations."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Upsert (insert)
        upserted = await db.upsert("record:1", {"value": "first"})
        assert upserted is not None

        # Upsert (update)
        upserted = await db.upsert("record:1", {"value": "second"})
        assert upserted is not None


@pytest.mark.asyncio
async def test_insert_operation() -> None:
    """Test insert operations."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Insert single
        inserted = await db.insert("entry", {"data": "test"})
        assert inserted is not None

        # Insert multiple
        inserted = await db.insert("entry", [{"data": "test1"}, {"data": "test2"}])
        assert inserted is not None


@pytest.mark.asyncio
async def test_connection_lifecycle() -> None:
    """Test connection lifecycle management."""
    db = AsyncSurreal("mem://")

    # Connect
    await db.connect("mem://")
    await db.use("test", "test")

    # Use
    await db.create("test", {"value": 1})

    # Close
    await db.close()


@pytest.mark.asyncio
async def test_invalidate() -> None:
    """Test session invalidation."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        # Invalidate session
        await db.invalidate()
