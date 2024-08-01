from unittest import TestCase, main

from surrealdb import AsyncSurrealDB
from tests.integration.url import Url
import asyncio


class TestInvalidate(TestCase):

    def setUp(self):
        self.connection = AsyncSurrealDB(Url().url)

    def tearDown(self):
        async def teardown_queries():
            for query in self.queries:
                await self.connection.query(query)

        asyncio.run(teardown_queries())

    def test_invalidate(self):
        self.queries = ["DELETE user;"]
        async def run():
            await self.connection.connect()
            await self.connection.query("CREATE user:tobie SET name = 'Tobie';")
            await self.connection.query("CREATE user:jaime SET name = 'Jaime';")

            outcome = await self.connection.query("SELECT * FROM user;")
            self.assertEqual(
                [
                    {"id": "user:jaime", "name": "Jaime"},
                    {"id": "user:tobie", "name": "Tobie"},
                ],
                outcome,
            )

            await self.connection.invalidate()
            outcome = await self.connection.query("SELECT * FROM user;")
            self.assertEqual(
                [
                    {"id": "user:jaime", "name": "Jaime"},
                    {"id": "user:tobie", "name": "Tobie"},
                ],
                outcome,
            )
        asyncio.run(run())


if __name__ == "__main__":
    main()
