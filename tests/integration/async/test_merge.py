"""
Tests the Update operation of the AsyncSurrealDB class with query and merge function.
"""

from typing import List
from unittest import IsolatedAsyncioTestCase, main

from surrealdb import AsyncSurrealDB
from tests.integration.connection_params import TestConnectionParams


class TestAsyncHttpMerge(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.params = TestConnectionParams()
        self.db = AsyncSurrealDB(self.params.url)

        self.queries: List[str] = []

        await self.db.connect()
        await self.db.use(self.params.namespace, self.params.database)
        await self.db.sign_in("root", "root")

    async def asyncTearDown(self):
        for query in self.queries:
            await self.db.query(query)

        await self.db.close()

    async def test_merge_person_with_tags(self):
        self.queries = ["DELETE user;"]

        await self.db.query("CREATE user:tobie SET name = 'Tobie';")
        await self.db.query("CREATE user:jaime SET name = 'Jaime';")

        _ = await self.db.merge(
            "user",
            {
                "active": True,
            },
        )

        outcome = await self.db.query("SELECT * FROM user;")
        self.assertEqual(
            [
                {"active": True, "id": "user:jaime", "name": "Jaime"},
                {"active": True, "id": "user:tobie", "name": "Tobie"},
            ],
            outcome[0]['result']

        )


if __name__ == "__main__":
    main()
