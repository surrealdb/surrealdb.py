"""
Handles the integration tests for logging into the database.
"""

from unittest import IsolatedAsyncioTestCase, main

from surrealdb import AsyncSurrealDB, SurrealDbConnectionError
from tests.integration.connection_params import TestConnectionParams


class TestAsyncAuth(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.params = TestConnectionParams()
        self.db = AsyncSurrealDB(self.params.url)

        await self.db.connect()
        await self.db.use(self.params.namespace, self.params.database)

    async def asyncTearDown(self):
        await self.db.close()

    async def test_login_success(self):
        outcome = await self.db.sign_in("root", "root")
        self.assertNotEqual(None, outcome)

    async def test_login_wrong_password(self):
        with self.assertRaises(SurrealDbConnectionError) as context:
            await self.db.sign_in("root", "wrong")

        self.assertEqual(True, "There was a problem with authentication" in str(context.exception))

    async def test_login_wrong_username(self):
        with self.assertRaises(SurrealDbConnectionError) as context:
            await self.db.sign_in("wrong", "root")

        self.assertEqual(True, "There was a problem with authentication" in str(context.exception))


if __name__ == "__main__":
    main()
