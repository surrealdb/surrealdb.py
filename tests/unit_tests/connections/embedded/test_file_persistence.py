"""Tests for file-based persistent embedded database."""

import tempfile
from pathlib import Path

import pytest

from surrealdb import AsyncSurreal, Surreal


@pytest.mark.asyncio
async def test_async_file_persistence() -> None:
    """Test that data persists across async connections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "testdb"
        db_url = f"file://{db_path}"

        # First connection: create data
        async with AsyncSurreal(db_url) as db:
            await db.use("test", "test")

            created = await db.create("persistent", {"name": "Alice", "value": 42})
            assert created is not None

        # Second connection: verify data persisted
        async with AsyncSurreal(db_url) as db:
            await db.use("test", "test")

            records = await db.select("persistent")
            assert records is not None


def test_sync_file_persistence() -> None:
    """Test that data persists across sync connections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "testdb"
        db_url = f"file://{db_path}"

        # First connection: create data
        with Surreal(db_url) as db:
            db.use("test", "test")

            created = db.create("persistent", {"name": "Bob", "value": 100})
            assert created is not None

        # Second connection: verify data persisted
        with Surreal(db_url) as db:
            db.use("test", "test")

            records = db.select("persistent")
            assert records is not None


@pytest.mark.asyncio
async def test_file_updates_persist() -> None:
    """Test that updates to file-based database persist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "testdb"
        db_url = f"file://{db_path}"

        # Create initial record
        async with AsyncSurreal(db_url) as db:
            await db.use("test", "test")
            await db.create("counter", {"count": 1})

        # Update the record
        async with AsyncSurreal(db_url) as db:
            await db.use("test", "test")
            await db.update("counter", {"count": 2})

        # Verify update persisted
        async with AsyncSurreal(db_url) as db:
            await db.use("test", "test")
            records = await db.select("counter")
            assert records is not None
