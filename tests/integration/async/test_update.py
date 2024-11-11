"""
Tests the Update operation of the AsyncSurrealDB class with query and update function.
"""

import asyncio
from typing import List
from unittest import TestCase, main

from surrealdb import AsyncSurrealDB
from tests.integration.url import Url


class TestAsyncUpdate(TestCase):
    def setUp(self):
        self.db = AsyncSurrealDB(Url().url)
        self.queries: List[str] = []

        async def login():
            await self.db.connect()
            await self.db.sign_in(
                {
                    "username": "root",
                    "password": "root",
                }
            )

        asyncio.run(login())

    def tearDown(self):
        async def teardown_queries():
            for query in self.queries:
                await self.db.query(query)

        asyncio.run(teardown_queries())

    def test_update_ql(self):
        self.queries = ["DELETE user;"]

        async def update():
            await self.db.query("CREATE user:tobie SET name = 'Tobie';")
            await self.db.query("CREATE user:jaime SET name = 'Jaime';")
            outcome = await self.db.query(
                "UPDATE user SET lastname = 'Morgan Hitchcock';"
            )
            self.assertEqual(
                [
                    {
                        "id": "user:jaime",
                        "lastname": "Morgan Hitchcock",
                        "name": "Jaime",
                    },
                    {
                        "id": "user:tobie",
                        "lastname": "Morgan Hitchcock",
                        "name": "Tobie",
                    },
                ],
                outcome,
            )

        asyncio.run(update())

    def test_update_person_with_tags(self):
        self.queries = ["DELETE person;"]

        async def update_person_with_tags():
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
                    "id": "person:⟨失败⟩",
                    "user": "still me",
                    "pass": "*æ失败",
                    "really": False,
                    "tags": ["python", "test"],
                },
                outcome,
            )

        asyncio.run(update_person_with_tags())


if __name__ == "__main__":
    main()
