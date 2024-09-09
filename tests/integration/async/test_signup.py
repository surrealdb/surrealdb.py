"""
Handles the integration tests for logging into the database.
"""

import asyncio
import os
from unittest import TestCase, main
from typing import List

from surrealdb import AsyncSurrealDB
from tests.integration.url import Url


class TestAsyncSignup(TestCase):
    def setUp(self):
        self.queries: List[str] = []
        self.email = "john.doe@example.com"
        self.password = "password123"
        self.namespace = "namespace"
        self.database = "database"
        self.scope = "user_scope"
        self.connection = AsyncSurrealDB(Url().url)

    def tearDown(self):
        async def teardown_queries():
            for query in self.queries:
                await self.connection.query(query)

        asyncio.run(teardown_queries())

    def set_namespace(self):
        async def namespace():
            # await self.connection.connect()
            _ = await self.connection.use_database(self.database)
            _ = await self.connection.use_namespace(self.namespace)
        asyncio.run(namespace())

    def query(self):
        query_str = """
        DEFINE SCOPE user_scope SESSION 24h
        SIGNUP ( CREATE user SET email = $email, password = crypto::argon2::generate($password) )
        SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) )
        """
        async def _query():
            return await self.connection.query(query_str)
        return asyncio.run(_query())

    def signup(self):
        async def _signup():
            return await self.connection.signup(
                namespace=self.namespace,
                database=self.database,
                scope=self.scope,
                data={"email": self.email, "password": self.password},
            )
        return asyncio.run(_signup())


    async def login(self, username: str, password: str):
        await self.connection.connect()
        outcome = await self.connection.signin(
            {
                "username": username,
                "password": password,
            }
        )
        return outcome

    def test_signup(self):
        outcome = asyncio.run(self.login("root", "root"))
        self.set_namespace()

        _ = self.query()
        _outcome = self.signup()


if __name__ == "__main__":
    main()
