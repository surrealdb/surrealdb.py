from unittest import main, IsolatedAsyncioTestCase
import os
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
        self.main_connection = AsyncHttpSurrealConnection(self.url)
        _ = await self.main_connection.signin(self.vars_params)
        _ = await self.main_connection.use(namespace=self.namespace, database=self.database_name)
        await self.main_connection.query("DELETE user;")
        _ = await self.main_connection.query_raw("CREATE user:jaime SET name = 'Jaime';")

        self.connection = AsyncHttpSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(namespace=self.namespace, database=self.database_name)

    async def running_through_docker(self):
        _ = await self.connection.invalidate()
        with self.assertRaises(Exception) as context:
            _ = await self.connection.query("CREATE user:jaime SET name = 'Jaime';")
        self.assertEqual(
            "IAM error: Not enough permissions" in str(context.exception),
            True
        )

    async def running_through_binary(self):
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

    async def test_invalidate(self):
        if os.environ.get("DOCKER_RUN") == "TRUE":
            await self.running_through_docker()
        else:
            await self.running_through_binary()


if __name__ == "__main__":
    main()
