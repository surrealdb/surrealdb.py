from unittest import main, IsolatedAsyncioTestCase

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


class TestAsyncHttpSurrealConnection(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.url = "http://localhost:8000"
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
        _ = await self.connection.use(namespace=self.namespace, database=self.database_name)

    async def test_invalidate(self):
        _ = await self.connection.invalidate()
        with self.assertRaises(Exception) as context:
            _ = await self.connection.query("CREATE user:jaime SET name = 'Jaime';")
        self.assertEqual(
            "IAM error: Not enough permissions" in str(context.exception),
            True
        )


if __name__ == "__main__":
    main()
