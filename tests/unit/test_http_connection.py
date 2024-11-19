import logging
from unittest import TestCase

from surrealdb.connection_http import HTTPConnection


class TestWSConnection(TestCase):
    async def asyncSetUp(self):
        logger = logging.getLogger(__name__)

        http_con = HTTPConnection(base_url='http://localhost:8000', logger=logger)
        await http_con.connect()
        await http_con.send('signin', {'user': 'root', 'pass': 'root'})
