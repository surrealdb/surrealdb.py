"""
Handles the integration tests for creating and deleting using the create function and QL, and delete in QL.
"""

from typing import List
from unittest import IsolatedAsyncioTestCase, main

from surrealdb import AsyncSurrealDB, RecordID
from tests.integration.connection_params import TestConnectionParams


class TestAsyncCreate(IsolatedAsyncioTestCase):
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

    async def test_create_ql(self):
        self.queries = ["DELETE user;"]

        await self.db.query("CREATE user:tobie SET name = 'Tobie';")
        await self.db.query("CREATE user:jaime SET name = 'Jaime';")

        outcome = await self.db.query("SELECT * FROM user;")
        self.assertEqual(
            [
                {"id": RecordID('user', 'jaime'), "name": "Jaime"},
                {"id": RecordID('user', 'tobie'), "name": "Tobie"},
            ],
            outcome[0]['result'],
        )

    async def test_delete_ql(self):
        self.queries = ["DELETE user;"]
        await self.test_create_ql()

        outcome = await self.db.query("DELETE user;")
        self.assertEqual([], outcome[0]['result'])

        outcome = await self.db.query("SELECT * FROM user;")
        self.assertEqual([], outcome[0]['result'])

    async def test_create_person_with_tags_ql(self):
        self.queries = ["DELETE person;"]

        outcome = await self.db.query(
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
        self.assertEqual(
            [
                {
                    "id": RecordID.parse("person:⟨失败⟩"),
                    "pass": "*æ失败",
                    "really": True,
                    "tags": ["python", "documentation"],
                    "user": "me",
                }
            ],
            outcome[0]['result'],
        )

    async def test_create_person_with_tags(self):
        self.queries = ["DELETE person;"]

        outcome = await self.db.create(
            "person:`失败`",
            {
                "user": "still me",
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
            },
        )
        self.assertEqual(
            {
                "id": RecordID.parse("person:⟨失败⟩"),
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
                "user": "still me",
            },
            outcome,
        )


if __name__ == "__main__":
    main()
