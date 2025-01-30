import asyncio
from asyncio import TimeoutError
from unittest import main, IsolatedAsyncioTestCase
from uuid import UUID

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import RecordID


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
        await self.connection.signin(self.vars_params)
        await self.connection.use(namespace=self.namespace, database=self.database_name)
        await self.connection.query("DELETE user;")
        await self.connection.query("CREATE user:tobie SET name = 'Tobie';")
        self.pub_connection = AsyncWsSurrealConnection(self.url)
        await self.pub_connection.signin(self.vars_params)
        await self.pub_connection.use(namespace=self.namespace, database=self.database_name)

    async def test_live_subscription(self):
        # Start the live query
        query_uuid = await self.connection.live("user")
        self.assertIsInstance(query_uuid, UUID)

        # Start the live subscription
        subscription = self.connection.subscribe_live(query_uuid)

        # Push an update
        await self.pub_connection.query("CREATE user:jaime SET name = 'Jaime';")

        try:
            update = await asyncio.wait_for(subscription.__anext__(), timeout=10)
            self.assertEqual(update["name"], "Jaime")
            self.assertEqual(update["id"], RecordID("user", "jaime"))
        except TimeoutError:
            self.fail("Timed out waiting for live subscription update")

        await self.pub_connection.kill(query_uuid)

        # Cleanup the subscription
        await self.pub_connection.query("DELETE user;")
        await self.pub_connection.socket.close()
        await self.connection.socket.close()


if __name__ == "__main__":
    main()
