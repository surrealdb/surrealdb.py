from unittest import IsolatedAsyncioTestCase, main

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


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
        self.data = {"name": "Jaime", "age": 35}
        self.record_id = RecordID("person", "tobie")
        self.connection = AsyncHttpSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )
        await self.connection.query("DELETE person;")
        await self.connection.query("CREATE person:tobie SET name = 'Tobie';")

    async def asyncTearDown(self):
        if self.connection:
            await self.connection.close()

    def check_no_change(self, data: dict):
        self.assertEqual(self.record_id, data["id"])
        self.assertEqual("Tobie", data["name"])

    def check_change(self, data: dict):
        self.assertEqual(self.record_id, data["id"])

        self.assertEqual("Jaime", data["name"])
        self.assertEqual(35, data["age"])

    async def test_delete_string(self):
        outcome = await self.connection.delete("person:tobie")
        self.check_no_change(outcome)
        outcome = await self.connection.query("SELECT * FROM person;")
        self.assertEqual(outcome, [])

    async def test_delete_record_id(self):
        first_outcome = await self.connection.delete(self.record_id)
        self.check_no_change(first_outcome)
        outcome = await self.connection.query("SELECT * FROM person;")
        self.assertEqual(outcome, [])

    async def test_delete_table(self):
        await self.connection.query("CREATE person:jaime SET name = 'Jaime';")
        table = Table("person")
        first_outcome = await self.connection.delete(table)
        self.assertEqual(2, len(first_outcome))
        outcome = await self.connection.query("SELECT * FROM person;")
        self.assertEqual(outcome, [])


if __name__ == "__main__":
    main()
