import asyncio
import logging

from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from surrealdb.connection_ws import WebsocketConnection
from surrealdb.data.cbor import encode, decode


class TestWSConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger = logging.getLogger(__name__)
        self.ws_con = WebsocketConnection(base_url='ws://localhost:8000', logger=logger, encoder=encode, decoder=decode)
        await self.ws_con.connect()

    async def asyncTearDown(self):
        await self.ws_con.send("query", "DELETE users;")
        await self.ws_con.close()

    async def test_one(self):
        await self.ws_con.use("test", "test")
        token = await self.ws_con.send('signin', {'user': 'root', 'pass': 'root'})
        await self.ws_con.unset("root")
        print("Test set")

    async def test_create_response_queue(self):
        self.ws_con[1] = {}

    async def test_send(self):
        await self.ws_con.use("test", "test")
        token = await self.ws_con.send('signin', {'user': 'root', 'pass': 'root'})
        self.ws_con.set_token(token)

        live_id = await self.ws_con.send("live", "users")
        live_queue = await self.ws_con.live_notifications(live_id)

        await self.ws_con.send("query", "CREATE users;")

        notification_data = await asyncio.wait_for(live_queue.get(), 10)  # Set timeout
        self.assertEqual(notification_data.get("id"), live_id)
        self.assertEqual(notification_data.get("action"), "CREATE")
