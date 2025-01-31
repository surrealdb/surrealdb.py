from unittest import main, IsolatedAsyncioTestCase

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
        self.main_connection = AsyncWsSurrealConnection(self.url)
        _ = await self.main_connection.signin(self.vars_params)
        _ = await self.main_connection.use(namespace=self.namespace, database=self.database_name)
        await self.main_connection.query("DELETE user;")
        _ = await self.main_connection.query_raw("CREATE user:jaime SET name = 'Jaime';")

        self.connection = AsyncWsSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(namespace=self.namespace, database=self.database_name)

    async def test_invalidate(self):
        outcome = await self.connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))
        outcome = await self.main_connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))

        _ = await self.connection.invalidate()

        outcome = await self.connection.query("SELECT * FROM user;")
        self.assertEqual(0, len(outcome))
        outcome = await self.main_connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))

        await self.main_connection.query("DELETE user;")
        await self.main_connection.close()
        await self.connection.close()


if __name__ == "__main__":
    main()
