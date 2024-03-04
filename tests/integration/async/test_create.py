"""
Handles the integration tests for creating and deleting using the create function and QL, and delete in QL.
"""
import asyncio
from typing import List
from unittest import TestCase, main

from surrealdb import AsyncSurrealDB
from tests.integration.url import Url


class TestAsyncCreate(TestCase):

    def setUp(self):
        self.connection = AsyncSurrealDB(Url().url)
        self.queries: List[str] = []

        async def login():
            await self.connection.connect()
            await self.connection.signin({
                "username": "root",
                "password": "root",
            })

        asyncio.run(login())

    def tearDown(self):
        async def teardown_queries():
            for query in self.queries:
                await self.connection.query(query)

        asyncio.run(teardown_queries())

    def test_create_ql(self):
        self.queries = ["DELETE user;"]

        async def create():
            await self.connection.query("CREATE user:tobie SET name = 'Tobie';")
            await self.connection.query("CREATE user:jaime SET name = 'Jaime';")

            outcome = await self.connection.query("SELECT * FROM user;")
            self.assertEqual(
                [{'id': 'user:jaime', 'name': 'Jaime'}, {'id': 'user:tobie', 'name': 'Tobie'}],
                outcome
            )
        asyncio.run(create())

    def test_delete_ql(self):
        self.queries = ["DELETE user;"]
        self.test_create_ql()

        async def delete():
            outcome = await self.connection.query("DELETE user;")
            self.assertEqual([], outcome)

            outcome = await self.connection.query("SELECT * FROM user;")
            self.assertEqual([], outcome)

        asyncio.run(delete())

    def test_create_person_with_tags_ql(self):
        self.queries = ["DELETE person;"]

        async def create_person_with_tags():
            outcome = await self.connection.query(
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
                [{"id": "person:⟨失败⟩", "pass": "*æ失败", "really": True, "tags": [ "python", "documentation" ], "user": "me" }],
                outcome
            )
        asyncio.run(create_person_with_tags())

    def test_create_person_with_tags(self):
        self.queries = ["DELETE person;"]

        async def create_person_with_tags():
            outcome = await self.connection.create(
                "person:`失败`",
                {
                    "user": "still me",
                    "pass": "*æ失败",
                    "really": False,
                    "tags": ["python", "test"],
                }
            )
            self.assertEqual(
                {"id": "person:⟨失败⟩", "pass": "*æ失败", "really": False, "tags": ["python", "test"],
                 "user": "still me"},
                outcome
            )

        asyncio.run(create_person_with_tags())


if __name__ == '__main__':
    main()
