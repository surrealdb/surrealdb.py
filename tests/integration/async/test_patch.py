"""
Tests the Patch operation of the AsyncSurrealDB class with query and update function.
"""
import asyncio
import datetime
from typing import List
from unittest import TestCase, main

from surrealdb import AsyncSurrealDB
from tests.integration.url import Url


class TestAsyncPatch(TestCase):
    def setUp(self):
        self.connection = AsyncSurrealDB(Url().url)
        self.queries: List[str] = []

        async def login():
            await self.connection.connect()
            await self.connection.signin(
                {
                    "username": "root",
                    "password": "root",
                }
            )

        asyncio.run(login())

    def tearDown(self):
        async def teardown_queries():
            for query in self.queries:
                await self.connection.query(query)

        asyncio.run(teardown_queries())

    def test_patch(self):
        self.queries = ["DELETE person;"]
        async def run_test():
            await self.connection.create("person")
            now = str(datetime.datetime.utcnow())
            outcome = await self.connection.patch("person", [{
                'op': "replace",
                'path': "/created_at",
                'value': now
            }])
            self.assertEqual(
                now,
                outcome[0]["created_at"]
            )

        asyncio.run(run_test())

    def test_complex_patch(self):
        self.queries = ["DELETE person;"]

        async def run_test():
            await self.connection.create("person")
            outcome = await self.connection.patch('person:tobie', [
                 { 'op': "replace", 'path': "/settings/active", 'value': False },
                 { 'op': "add", "path": "/tags", "value": ["developer", "engineer"] },
                 { 'op': "remove", "path": "/temp" },
            ])
            self.assertEqual(
                {
                    "id": 'person:tobie',
                    "settings": {"active": False},
                    "tags": ["developer", "engineer"]
                },
                outcome
            )

        asyncio.run(run_test())

    def test_complex_patch_context(self):
        self.queries = ["DELETE person;"]

        async def run_test():
            async with self.connection as temp_con:
                await temp_con.create("person")
                outcome = await temp_con.patch('person:tobie', [
                     { 'op': "replace", 'path': "/settings/active", 'value': False },
                     { 'op': "add", "path": "/tags", "value": ["developer", "engineer"] },
                     { 'op': "remove", "path": "/temp" },
                ])
                self.assertEqual(
                    {
                        "id": 'person:tobie',
                        "settings": {"active": False},
                        "tags": ["developer", "engineer"]
                    },
                    outcome
                )

        asyncio.run(run_test())


if __name__ == "__main__":
    main()
