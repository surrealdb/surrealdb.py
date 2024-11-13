from unittest import TestCase

from surrealdb.connection_http import HTTPConnection


class TestWSConnection(TestCase):
    async def asyncSetup(self):
        http_con = HTTPConnection(base_url='http://localhost:8000', namespace='test', database='test')
        await http_con.connect()
        await http_con.send('signin', {'user': 'root', 'pass': 'root'})
