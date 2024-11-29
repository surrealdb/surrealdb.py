"""
Tests the Update operation of the AsyncSurrealDB class with query and update function.
"""

from typing import List
from unittest import IsolatedAsyncioTestCase, main

from surrealdb import AsyncSurrealDB, RecordID
from tests.integration.connection_params import TestConnectionParams


class TestAsyncUpdate(IsolatedAsyncioTestCase):
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

    async def test_update_ql(self):
        self.queries = ["DELETE user;"]

        await self.db.query("CREATE user:tobie SET name = 'Tobie';")
        await self.db.query("CREATE user:jaime SET name = 'Jaime';")
        outcome = await self.db.query(
            "UPDATE user SET lastname = 'Morgan Hitchcock';"
        )
        self.assertEqual(
            [
                {
                    "id": RecordID.parse("user:jaime"),
                    "lastname": "Morgan Hitchcock",
                    "name": "Jaime",
                },
                {
                    "id": RecordID.parse("user:tobie"),
                    "lastname": "Morgan Hitchcock",
                    "name": "Tobie",
                },
            ],
            outcome[0]['result'],
        )

    async def test_update_person_with_tags(self):
        self.queries = ["DELETE person;"]

        _ = await self.db.query(
            """
            CREATE person:`失败` CONTENT
            {
                "user": "me",
                "pass": "*æ失败",
                "really": True,
                "tags": ["python", "documentation"],
            };
            """
        )

        outcome = await self.db.update(
            # "person:`失败`",
            RecordID.parse("person:失败"),
            {
                "user": "still me",
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
            },
        )
        self.assertEqual(
            {
                "id": RecordID.parse("person:失败"),
                "user": "still me",
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
            },
            outcome,
        )


if __name__ == "__main__":
    main()
