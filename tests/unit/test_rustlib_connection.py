import logging
import rust_surrealdb

from unittest import IsolatedAsyncioTestCase
from surrealdb.connection_http import HTTPConnection
from surrealdb.data.cbor import encode, decode


class TestHTTPConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger = logging.getLogger(__name__)

    async def test_default_method(self):
        print(rust_surrealdb.sum_as_string(1, 2))
        # rust_surrealdb.connect("memory", 10)
        obj = rust_surrealdb.MyStruct(42)
        obj.set_value(20)
        print(obj.get_value())
