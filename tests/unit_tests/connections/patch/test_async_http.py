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
        self.record_id = RecordID(table_name="user", identifier="tobie")
        self.data = [
            {"op": "replace", "path": "/name", "value": "Jaime"},
            {"op": "replace", "path": "/age", "value": 35},
        ]
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

    async def test_patch_string_with_data(self):
        outcome = await self.connection.patch("user:tobie", self.data)
        self.check_change(outcome)
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])
        await self.connection.query("DELETE user;")

    async def test_patch_record_id_with_data(self):
        outcome = await self.connection.patch(self.record_id, self.data)
        self.check_change(outcome)
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])
        await self.connection.query("DELETE user;")

    async def test_patch_table_with_data(self):
        table = Table("user")
        outcome = await self.connection.patch(table, self.data)
        self.check_change(outcome[0])
        outcome = await self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])
        await self.connection.query("DELETE user;")


if __name__ == "__main__":
    main()
