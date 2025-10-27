"""Basic sync embedded SurrealDB example using in-memory database."""

from surrealdb import Surreal


def main() -> None:
    """Run basic sync embedded database operations."""
    # Create an in-memory database
    with Surreal("mem://") as db:
        # Use a namespace and database
        db.use("test", "test")

        # Note: Embedded databases don't require authentication

        # Create a person
        person = db.create(
            "person", {"name": "Jane Smith", "age": 28, "email": "jane@example.com"}
        )
        print(f"Created person: {person}")

        # Query all people
        people = db.select("person")
        print(f"All people: {people}")

        # Update the person
        updated = db.update(
            "person", {"name": "Jane Smith", "age": 29, "email": "jane@example.com"}
        )
        print(f"Updated person: {updated}")

        # Run a SurrealQL query
        result = db.query(
            """
            SELECT * FROM person WHERE age < $max_age
        """,
            {"max_age": 30},
        )
        print(f"Query result: {result}")

        # Delete all people
        db.delete("person")
        print("Deleted all people")


if __name__ == "__main__":
    main()
