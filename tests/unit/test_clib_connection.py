from unittest import IsolatedAsyncioTestCase
from logging import getLogger
from surrealdb.connection_clib import CLibConnection
from surrealdb.data.cbor import encode, decode


class TestCLibConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger = getLogger(__name__)

        self.clib = CLibConnection(base_url='surrealkv://', logger=self.logger, encoder=encode, decoder=decode)
        await self.clib.connect()

    async def test_send(self):
        await self.clib.send('use', "test_ns", "test_db")
