import asyncio

from surrealdb import AsyncSurrealDB

async def main():
    async with AsyncSurrealDB("ws://localhost:8000") as db:
        db.sign_in("root", "root")
        db.use("example_ns", "example_db")

        upsert_data = {"name": "Charlie", "age": 35}
        result = db.upsert("users", upsert_data)
        print(f"Upsert Result: {result}")

if __name__ == '__main__':
    asyncio.run(main())