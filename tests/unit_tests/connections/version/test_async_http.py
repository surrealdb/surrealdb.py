from unittest import IsolatedAsyncioTestCase, main

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


class TestAsyncWsSurrealConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.url = "ws://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.connection = AsyncHttpSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )

    async def test_version(self):
        self.assertEqual(str, type(await self.connection.version()))


if __name__ == "__main__":
    main()
