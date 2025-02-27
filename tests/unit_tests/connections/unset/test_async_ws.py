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
        self.connection = AsyncWsSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(namespace=self.namespace, database=self.database_name)

    async def test_unset(self):
        await self.connection.query("DELETE person;")
        outcome = await self.connection.let('name', {
            "first": 'Tobie',
            "last": 'Morgan Hitchcock',
        })
        self.assertEqual(None, outcome)
        await self.connection.query('CREATE person SET name = $name')
        outcome = await self.connection.query('SELECT * FROM person WHERE name.first = $name.first')
        self.assertEqual(1, len(outcome))
        self.assertEqual({'first': 'Tobie', 'last': 'Morgan Hitchcock'}, outcome[0]["name"])

        await self.connection.unset(key="name")

        # because the key was unset then $name.first is None returning []
        outcome = await self.connection.query('SELECT * FROM person WHERE name.first = $name.first')
        self.assertEqual([], outcome)

        await self.connection.query("DELETE person;")


if __name__ == "__main__":
    main()
