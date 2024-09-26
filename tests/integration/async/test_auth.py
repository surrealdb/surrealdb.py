"""
Handles the integration tests for logging into the database.
"""

import asyncio
import os
from unittest import TestCase, main

from surrealdb import AsyncSurrealDB
from tests.integration.url import Url


class TestAsyncAuth(TestCase):
    def setUp(self):
        self.connection = AsyncSurrealDB(Url().url)

    def tearDown(self):
        pass

    async def login(self, username: str, password: str):
        await self.connection.connect()
        outcome = await self.connection.signin(
            {
                "username": username,
                "password": password,
            }
        )
        return outcome

    def test_login_success(self):
        outcome = asyncio.run(self.login("root", "root"))
        self.assertEqual(None, outcome)

    def test_login_wrong_password(self):
        with self.assertRaises(RuntimeError) as context:
            asyncio.run(self.login("root", "wrong"))

        self.assertEqual( True,
            'There was a problem with authentication' in str(context.exception)
        )

    def test_login_wrong_username(self):
        with self.assertRaises(RuntimeError) as context:
            asyncio.run(self.login("wrong", "root"))

        self.assertEqual( True,
            'There was a problem with authentication' in str(context.exception)
        )


if __name__ == "__main__":
    main()
