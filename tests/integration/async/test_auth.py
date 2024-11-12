"""
Handles the integration tests for logging into the database.
"""

import asyncio
import os
from unittest import TestCase, main

from surrealdb import AsyncSurrealDB
from tests.integration.connection_params import TestConnectionParams


class TestAsyncAuth(TestCase):
    def setUp(self):
        self.params = TestConnectionParams()
        self.db = AsyncSurrealDB(self.params.url)

    def tearDown(self):
        pass

    async def login(self, username: str, password: str):
        await self.db.connect()
        outcome = await self.db.sign_in(username, password)
        return outcome

    def test_login_success(self):
        outcome = asyncio.run(self.login("root", "root"))
        self.assertEqual(None, outcome)

    def test_login_wrong_password(self):
        with self.assertRaises(RuntimeError) as context:
            asyncio.run(self.login("root", "wrong"))

        if os.environ.get("CONNECTION_PROTOCOL", "http") == "http":
            self.assertEqual(True, "(401 Unauthorized)" in str(context.exception))
        else:
            self.assertEqual(
                '"There was a problem with authentication"', str(context.exception)
            )

    def test_login_wrong_username(self):
        with self.assertRaises(RuntimeError) as context:
            asyncio.run(self.login("wrong", "root"))

        if os.environ.get("CONNECTION_PROTOCOL", "http") == "http":
            self.assertEqual(True, "(401 Unauthorized)" in str(context.exception))
        else:
            self.assertEqual(
                '"There was a problem with authentication"', str(context.exception)
            )


if __name__ == "__main__":
    main()
