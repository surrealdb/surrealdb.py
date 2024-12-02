import asyncio
from surrealdb import AsyncSurrealDB


async def main():
    async with AsyncSurrealDB(url="ws://localhost:8000") as db:
        await db.sign_in("root", "root")
        await db.use("test", "test")

        query = "SELECT * FROM users WHERE age > min_age;"
        variables = {"min_age": 25}

        results = await db.query(query, variables)
        print(f"Query Results: {results}")


asyncio.run(main())
