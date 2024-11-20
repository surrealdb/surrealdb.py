import logging
from unittest import IsolatedAsyncioTestCase

from surrealdb.connection_ws import WebsocketConnection


class TestWSConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger = logging.getLogger(__name__)
        self.ws_con = WebsocketConnection(base_url='ws://localhost:8000', logger=logger)
        await self.ws_con.connect()

    async def test_send(self):
        await self.ws_con.use("test", "test")
        token = await self.ws_con.send('signin', {'user': 'root', 'pass': 'root'})
        self.ws_con.set_token(token)

        live_id = await self.ws_con.send("live", "users")
        print("Live id: ", live_id)

        queue = await self.ws_con.live_notifications(live_id)
        # while True:
        #     data = await queue.get()
        #     print(data)



