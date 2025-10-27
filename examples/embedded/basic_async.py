"""Basic async embedded SurrealDB example using in-memory database."""

import asyncio

from surrealdb import AsyncSurreal


async def main() -> None:
    """Run basic async embedded database operations."""
    # Create an in-memory database
    async with AsyncSurreal("mem://") as db:
        # Use a namespace and database
        await db.use("test", "test")

        # Note: Embedded databases don't require authentication

        # Create a person
        person = await db.create(
            "person", {"name": "John Doe", "age": 30, "email": "john@example.com"}
        )
        print(f"Created person: {person}")

        # Query all people
        people = await db.select("person")
        print(f"All people: {people}")

        # Update the person
        updated = await db.update(
            "person", {"name": "John Doe", "age": 31, "email": "john@example.com"}
        )
        print(f"Updated person: {updated}")

        # Run a SurrealQL query
        result = await db.query(
            """
            SELECT * FROM person WHERE age > $min_age
        """,
            {"min_age": 25},
        )
        print(f"Query result: {result}")

        # Delete all people
        await db.delete("person")
        print("Deleted all people")


if __name__ == "__main__":
    asyncio.run(main())
