from unittest import TestCase

from surrealdb.data.types.datetime import DateTimeCompact
from surrealdb.data.cbor import encode, decode


class TestCBOR(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_datetime(self):
        compact_date_time_array = [1733994058, 83988472] # December 12, 2024 9:00:58.083 AM

        compact_date_time = DateTimeCompact.parse(compact_date_time_array[0], compact_date_time_array[1])
        encoded = encode(compact_date_time)
        decoded = decode(encoded)

        self.assertEqual(decoded.get_date_time(), '2024-12-12T10:00:58.083988Z')


