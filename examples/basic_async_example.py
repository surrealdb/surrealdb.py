from surrealdb import AsyncSurrealDB


async def main():
    """Example of how to use the SurrealDB client."""
    async with AsyncSurrealDB("ws://localhost:8000") as db:
        await db.use("test", "test")
        await db.sign_in("root", "root")

        print("Using methods")
        print("create: ", await db.create(
            "person",
            {
                "user": "me",
                "pass": "safe",
                "marketing": True,
                "tags": ["python", "documentation"],
            },
        ))
        print("read: ", await db.select("person"))
        print("update: ", await db.update("person", {
            "user": "you",
            "pass": "very_safe",
            "marketing": False,
            "tags": ["Awesome"]
        }))
        print("delete: ", await db.delete("person"))

        # You can also use the query method
        # doing all of the above and more in SurrealQl

        # In SurrealQL you can do a direct insert
        # and the table will be created if it doesn't exist
        print("Using justawait db.query")
        print("create: ", await db.query("""
        insert into person {
            user: 'me',
            pass: 'very_safe',
            tags: ['python', 'documentation']
        };

        """))
        print("read: ", await db.query("select * from person"))

        print("update: ", await db.query("""
        update person content {
            user: 'you',
            pass: 'more_safe',
            tags: ['awesome']
        };

        """))
        print("delete: ", await db.query("delete person"))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
