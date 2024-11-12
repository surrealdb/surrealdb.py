from unittest import TestCase

from surrealdb.ws import WebsocketConnection


class TestWSConnection(TestCase):
    def setup(self):
        ws_con = WebsocketConnection(base_url='ws://localhost:8000', namespace='test', database='test')
        await ws_con.connect()
        await ws_con.send('signin', {'user': 'root', 'pass': 'root'})