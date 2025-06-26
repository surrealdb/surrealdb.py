from unittest import IsolatedAsyncioTestCase, main

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID


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
        self.data = {
            "username": self.username,
            "password": self.password,
        }
        self.insert_bulk_data = [
            {
                "name": "Tobie",
            },
            {"name": "Jaime"},
        ]
        self.insert_data = [
            {
                "name": "Tobie",
            }
        ]
        self.connection = AsyncHttpSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )
        await self.connection.query("DELETE user;")

    async def test_insert_string_with_data(self):
        outcome = await self.connection.insert("user", self.insert_bulk_data)
        self.assertEqual(2, len(outcome))
        self.assertEqual(len(await self.connection.query("SELECT * FROM user;")), 2)
        await self.connection.query("DELETE user;")

    async def test_insert_record_id_result_error(self):
        record_id = RecordID("user", "tobie")

        with self.assertRaises(Exception) as context:
            _ = await self.connection.insert(record_id, self.insert_data)
        e = str(context.exception)
        self.assertEqual(
            "There was a problem with the database: Can not execute INSERT statement using value"
            in e
            and "user:tobie" in e,
            True,
        )
        await self.connection.query("DELETE user;")


if __name__ == "__main__":
    main()
