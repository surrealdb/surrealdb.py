from unittest import IsolatedAsyncioTestCase, main

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.record_id import RecordID


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
        self.insert_bulk_data = [
            {
                "name": "Tobie",
                "email": "tobie@example.com",
                "enabled": True,
            },
            {
                "name": "Jaime",
                "email": "jaime@example.com",
                "enabled": True,
            },
        ]
        self.insert_data = [
            {
                "name": "Tobie",
                "email": "tobie@example.com",
                "enabled": True,
            }
        ]
        self.connection = AsyncWsSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )
        await self.connection.query("DELETE person;")

    async def asyncTearDown(self):
        if self.connection:
            await self.connection.close()

    async def test_insert_string_with_data(self):
        outcome = await self.connection.insert("person", self.insert_bulk_data)
        self.assertEqual(2, len(outcome))
        self.assertEqual(len(await self.connection.query("SELECT * FROM person;")), 2)
        await self.connection.query("DELETE person;")

    async def test_insert_record_id_result_error(self):
        record_id = RecordID("person", "tobie")

        with self.assertRaises(Exception) as context:
            _ = await self.connection.insert(record_id, self.insert_data)
        e = str(context.exception)
        self.assertEqual(
            "There was a problem with the database: Can not execute INSERT statement using value"
            in e
            and "person:tobie" in e,
            True,
        )
        await self.connection.query("DELETE person;")


if __name__ == "__main__":
    main()
