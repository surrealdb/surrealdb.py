from unittest import IsolatedAsyncioTestCase, main

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
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )

    async def test_select(self):
        await self.connection.query("DELETE user;")
        await self.connection.query("DELETE users;")

        await self.connection.query("CREATE user:tobie SET name = 'Tobie';")
        await self.connection.query("CREATE user:jaime SET name = 'Jaime';")

        await self.connection.query("CREATE users:one SET name = 'one';")
        await self.connection.query("CREATE users:two SET name = 'two';")

        outcome = await self.connection.select("user")
        self.assertEqual(
            outcome[0]["name"],
            "Jaime",
        )
        self.assertEqual(
            outcome[1]["name"],
            "Tobie",
        )
        self.assertEqual(2, len(outcome))

        await self.connection.query("DELETE user;")
        await self.connection.query("DELETE users;")


if __name__ == "__main__":
    main()
