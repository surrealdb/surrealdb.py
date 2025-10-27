"""File-based persistent embedded SurrealDB example."""

import asyncio
import tempfile
from pathlib import Path

from surrealdb import AsyncSurreal


async def main() -> None:
    """Run persistent file-based database operations."""
    # Create a temporary directory for the database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "mydb"
        db_url = f"file://{db_path}"

        print(f"Using database at: {db_path}")

        # First connection: create data
        print("\n=== First connection: Creating data ===")
        async with AsyncSurreal(db_url) as db:
            await db.use("test", "test")

            # Create some records
            await db.create(
                "company", {"name": "Acme Corp", "founded": 2020, "employees": 100}
            )

            await db.create(
                "company", {"name": "TechStart Inc", "founded": 2021, "employees": 50}
            )

            companies = await db.select("company")
            print(f"Created companies: {companies}")

        # Second connection: verify persistence
        print("\n=== Second connection: Verifying persistence ===")
        async with AsyncSurreal(db_url) as db:
            await db.use("test", "test")

            # Query the persisted data
            companies = await db.select("company")
            print(f"Loaded companies from disk: {companies}")

            # Update a company
            updated = await db.query("""
                UPDATE company SET employees = employees + 10 WHERE name = "Acme Corp"
            """)
            print(f"Updated company: {updated}")

            # Verify the update
            all_companies = await db.select("company")
            print(f"All companies after update: {all_companies}")

        print("\n=== Database file will be cleaned up automatically ===")


if __name__ == "__main__":
    asyncio.run(main())
