import base64
import logging
import uuid

import rust_surrealdb

from unittest import IsolatedAsyncioTestCase

from surrealdb.connection import request_id
from surrealdb.connection_http import HTTPConnection
from surrealdb.data.cbor import encode, decode


class TestHTTPConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger = logging.getLogger(__name__)

    async def test_default_method(self):
        enc_use = encode({
            "id": request_id(10),
            "method": "use",
            "params": ["test_ns", "test_db"],
        })
        res = ''.join(format(x, '02x') for x in enc_use)

        print(res)
        # print(rust_surrealdb.sum_as_string(1, 2))
        # try:
        #    con = rust_surrealdb.rust_connect("memory")
        # except Exception as e:
        #     print("Err")
