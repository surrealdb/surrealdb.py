import logging

from unittest import IsolatedAsyncioTestCase

from surrealdb.connection_http import HTTPConnection
from surrealdb.data.cbor import encode, decode


class TestHTTPConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger = logging.getLogger(__name__)

        self.http_con = HTTPConnection(base_url='http://localhost:8000', logger=logger, encoder=encode, decoder=decode)
        await self.http_con.connect()

    async def test_send(self):
        await self.http_con.use('test', 'test')
        _ = await self.http_con.send('signin', {'user': 'root', 'pass': 'root'})

    async def test_prepare_query_params(self):
        query_params = ("SOME SQL QUERY;", {
            "key1": "key1"
        })
        await self.http_con.set("key2", "key2")
        await self.http_con.set("key3", "key3")

        params = self.http_con._prepare_query_method_params(query_params)
        self.assertEqual(query_params[0], params[0])
        self.assertEqual({
            "key1": "key1",
            "key2": "key2",
            "key3": "key3",
        }, params[1])

        await self.http_con.unset("key3")

        params = self.http_con._prepare_query_method_params(query_params)
        self.assertEqual(query_params[0], params[0])
        self.assertEqual({
            "key1": "key1",
            "key2": "key2",
        }, params[1])

        await self.http_con.unset("key1")  # variable key not part of prev set variables

        params = self.http_con._prepare_query_method_params(query_params)
        self.assertEqual(query_params[0], params[0])
        self.assertEqual({
            "key1": "key1",
            "key2": "key2",
        }, params[1])
