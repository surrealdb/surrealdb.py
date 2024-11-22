import logging
from unittest import IsolatedAsyncioTestCase

from surrealdb.connection_http import HTTPConnection


class TestHTTPConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger = logging.getLogger(__name__)

        self.http_con = HTTPConnection(base_url='http://localhost:8000', logger=logger)
        await self.http_con.connect()

    async def test_send(self):
        await self.http_con.use('test', 'test')
        _ = await self.http_con.send('signin', {'user': 'root', 'pass': 'root'})
