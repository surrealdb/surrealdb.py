"""
Tests the Set operation of the AsyncSurrealDB class.
"""

from typing import List
from unittest import main, IsolatedAsyncioTestCase

from surrealdb import AsyncSurrealDB
from tests.integration.connection_params import TestConnectionParams


class TestAsyncSet(IsolatedAsyncioTestCase):

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

    async def test_set_ql(self):
        self.queries = ["DELETE person;"]
        query = "CREATE person:100 SET name = 'Tobie', company = 'SurrealDB', skills = ['Rust', 'Go', 'JavaScript'];"

        outcome = await self.db.query(query)
        self.assertEqual(
            [
                {
                    "id": "person:100",
                    "name": "Tobie",
                    "company": "SurrealDB",
                    "skills": ["Rust", "Go", "JavaScript"],
                }
            ],
            outcome[0]['result'],
        )

    async def test_set(self):
        self.queries = ["DELETE person;"]
        query = "CREATE person:100 SET name = $name;"

        _ = await self.db.set(
            "name",
            {
                "name": "Tobie",
                "last": "Morgan Hitchcock",
            },
        )
        _ = await self.db.query(query)
        outcome = await self.db.query("SELECT * FROM person;")
        self.assertEqual(
            [
                {
                    "id": "person:100",
                    "name": {"last": "Morgan Hitchcock", "name": "Tobie"},
                }
            ],
            outcome[0]['result'],
        )


if __name__ == "__main__":
    main()
