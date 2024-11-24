import asyncio
import logging

from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from surrealdb.connection_ws import WebsocketConnection


class TestWSConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger = logging.getLogger(__name__)
        self.ws_con = WebsocketConnection(base_url='ws://localhost:8000', logger=logger)
        await self.ws_con.connect()

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
        print("Live id: ", live_id)

        live_queue = await self.ws_con.live_notifications(live_id)

        await self.ws_con.send("query", "CREATE users;")

        notification_data = await asyncio.wait_for(live_queue.get(), 10)  # Set timeout
        self.assertEqual(notification_data.get("id"), live_id)
        self.assertEqual(notification_data.get("action"), "CREATE")
