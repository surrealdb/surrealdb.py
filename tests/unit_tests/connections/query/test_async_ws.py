from unittest import IsolatedAsyncioTestCase, main

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.record_id import RecordID


class TestAsyncWsSurrealConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.queries = ["DELETE user;"]
        self.url = "ws://localhost:8000/rpc"
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
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )

    async def test_query(self):
        await self.connection.query("DELETE user;")
        self.assertEqual(
            await self.connection.query("CREATE user:tobie SET name = 'Tobie';"),
            [{"id": RecordID(table_name="user", identifier="tobie"), "name": "Tobie"}],
        )
        self.assertEqual(
            await self.connection.query("CREATE user:jaime SET name = 'Jaime';"),
            [{"id": RecordID(table_name="user", identifier="jaime"), "name": "Jaime"}],
        )
        self.assertEqual(
            await self.connection.query("SELECT * FROM user;"),
            [
                {
                    "id": RecordID(table_name="user", identifier="jaime"),
                    "name": "Jaime",
                },
                {
                    "id": RecordID(table_name="user", identifier="tobie"),
                    "name": "Tobie",
                },
            ],
        )
        await self.connection.query("DELETE user;")


if __name__ == "__main__":
    main()
