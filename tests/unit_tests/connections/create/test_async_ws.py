from unittest import IsolatedAsyncioTestCase, main

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


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
        self.data = {
            "name": self.username,
            "password": self.password,
        }
        self.connection = AsyncWsSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )
        await self.connection.query("DELETE person;")

    async def asyncTearDown(self):
        if self.connection:
            await self.connection.close()

    async def test_create_string(self):
        outcome = await self.connection.create("person")
        self.assertEqual("person", outcome["id"].table_name)

        self.assertEqual(len(await self.connection.query("SELECT * FROM person;")), 1)
        await self.connection.query("DELETE person;")

    async def test_create_string_with_data(self):
        outcome = await self.connection.create("person", self.data)
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(self.password, outcome["password"])
        self.assertEqual(self.username, outcome["name"])

        outcome = await self.connection.query("SELECT * FROM person;")
        self.assertEqual(len(outcome), 1)
        self.assertEqual("person", outcome[0]["id"].table_name)
        self.assertEqual(self.password, outcome[0]["password"])
        self.assertEqual(self.username, outcome[0]["name"])

        await self.connection.query("DELETE person;")

    async def test_create_string_with_data_and_id(self):
        first_outcome = await self.connection.create("person:tobie", self.data)
        self.assertEqual("person", first_outcome["id"].table_name)
        self.assertEqual("tobie", first_outcome["id"].id)
        self.assertEqual(self.password, first_outcome["password"])
        self.assertEqual(self.username, first_outcome["name"])

        outcome = await self.connection.query("SELECT * FROM person;")
        self.assertEqual(len(outcome), 1)
        self.assertEqual("person", outcome[0]["id"].table_name)
        self.assertEqual("tobie", outcome[0]["id"].id)
        self.assertEqual(self.password, outcome[0]["password"])
        self.assertEqual(self.username, outcome[0]["name"])

        await self.connection.query("DELETE person;")

    async def test_create_record_id(self):
        record_id = RecordID("person", 1)
        outcome = await self.connection.create(record_id)
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(1, outcome["id"].id)

        self.assertEqual(len(await self.connection.query("SELECT * FROM person;")), 1)

        await self.connection.query("DELETE person;")

    async def test_create_record_id_with_data(self):
        record_id = RecordID("person", 1)
        outcome = await self.connection.create(record_id, self.data)
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(1, outcome["id"].id)
        self.assertEqual(self.password, outcome["password"])
        self.assertEqual(self.username, outcome["name"])

        outcome = await self.connection.query("SELECT * FROM person;")
        self.assertEqual(len(outcome), 1)
        self.assertEqual("person", outcome[0]["id"].table_name)
        self.assertEqual(self.password, outcome[0]["password"])
        self.assertEqual(self.username, outcome[0]["name"])

        await self.connection.query("DELETE person;")

    async def test_create_table(self):
        table = Table("person")
        outcome = await self.connection.create(table)
        self.assertEqual("person", outcome["id"].table_name)

        self.assertEqual(len(await self.connection.query("SELECT * FROM person;")), 1)

        await self.connection.query("DELETE person;")

    async def test_create_table_with_data(self):
        table = Table("person")
        outcome = await self.connection.create(table, self.data)
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(self.password, outcome["password"])
        self.assertEqual(self.username, outcome["name"])

        outcome = await self.connection.query("SELECT * FROM person;")
        self.assertEqual(len(outcome), 1)
        self.assertEqual("person", outcome[0]["id"].table_name)
        self.assertEqual(self.password, outcome[0]["password"])
        self.assertEqual(self.username, outcome[0]["name"])

        await self.connection.query("DELETE person;")


if __name__ == "__main__":
    main()
