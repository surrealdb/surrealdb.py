from unittest import IsolatedAsyncioTestCase, main
from uuid import UUID

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


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
        self.connection = AsyncWsSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )
        await self.connection.query("DELETE user;")
        await self.connection.query("CREATE user:tobie SET name = 'Tobie';")

    async def test_query(self):
        outcome = await self.connection.live("user")
        self.assertEqual(UUID, type(outcome))
        await self.connection.query("DELETE user;")


if __name__ == "__main__":
    main()
