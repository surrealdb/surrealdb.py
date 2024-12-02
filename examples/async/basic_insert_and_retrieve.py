import asyncio

from surrealdb import AsyncSurrealDB


async def main():
    db = AsyncSurrealDB("ws://localhost:8000")
    await db.connect()
    await db.use("example_ns", "example_db")
    await db.sign_in("root", "root")

    # Insert a record
    new_user = {"name": "Alice", "age": 30}
    inserted_record = await db.insert("users", new_user)
    print(f"Inserted Record: {inserted_record}")

    # Retrieve the record
    retrieved_users = await db.select("users")
    print(f"Retrieved Users: {retrieved_users}")

    await db.close()


if __name__ == '__main__':
    asyncio.run(main())
