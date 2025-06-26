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
        self.record_id = RecordID("user", "tobie")
        self.connection = AsyncHttpSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )
        await self.connection.query("DELETE user;")
        (await self.connection.query("CREATE user:tobie SET name = 'Tobie';"),)

    def check_no_change(self, data: dict):
        self.assertEqual(self.record_id, data["id"])
        self.assertEqual("Tobie", data["name"])

    def check_change(self, data: dict):
        self.assertEqual(self.record_id, data["id"])

        self.assertEqual("Jaime", data["name"])
        self.assertEqual(35, data["age"])

    async def test_update_string(self):
        outcome = await self.connection.update("user:tobie")
        self.assertEqual(outcome["id"], self.record_id)
        self.assertEqual(outcome["name"], "Tobie")
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_no_change(outcome[0])
        await self.connection.query("DELETE user;")

    async def test_update_string_with_data(self):
        first_outcome = await self.connection.update("user:tobie", self.data)
        self.check_change(first_outcome)
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])
        await self.connection.query("DELETE user;")

    async def test_update_record_id(self):
        first_outcome = await self.connection.update(self.record_id)
        self.check_no_change(first_outcome)
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_no_change(outcome[0])
        await self.connection.query("DELETE user;")

    async def test_update_record_id_with_data(self):
        outcome = await self.connection.update(self.record_id, self.data)
        self.check_change(outcome)
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])
        await self.connection.query("DELETE user;")

    async def test_update_table(self):
        table = Table("user")
        first_outcome = await self.connection.update(table)
        self.check_no_change(first_outcome[0])
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_no_change(outcome[0])

        await self.connection.query("DELETE user;")

    async def test_update_table_with_data(self):
        table = Table("user")
        outcome = await self.connection.update(table, self.data)
        self.check_change(outcome[0])
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])
        await self.connection.query("DELETE user;")


if __name__ == "__main__":
    main()
