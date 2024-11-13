from unittest import IsolatedAsyncioTestCase

from surrealdb.connection_ws import WebsocketConnection


class TestWSConnection(IsolatedAsyncioTestCase):
    async def asyncSetup(self):
        ws_con = WebsocketConnection(base_url='ws://localhost:8000', namespace='test', database='test')
        await ws_con.connect()
        await ws_con.send('signin', {'user': 'root', 'pass': 'root'})