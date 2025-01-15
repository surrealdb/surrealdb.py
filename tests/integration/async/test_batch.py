from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB, RecordID
from tests.integration.connection_params import TestConnectionParams
import asyncio
import websockets


class TestBatch(TestCase):

    def setUp(self) -> None:
        self.params = TestConnectionParams()
        self.db = SurrealDB(self.params.url)
        self.queries: List[str] = []

        self.db.connect()
        self.db.use(self.params.namespace, self.params.database)
        self.db.sign_in("root", "root")

        # self.query = """
        # CREATE |product:1000000| CONTENT {
        # name: rand::enum('Cruiser Hoodie', 'Surreal T-Shirt'),
        # colours: [rand::string(10), rand::string(10),],
        # price: rand::int(20, 60),
        # time: {
        #     created_at: rand::time(1611847404, 1706455404),
        #     updated_at: rand::time(1651155804, 1716906204)
        #     }
        # };
        # """
        # self.db.query(query=self.query)

    def tearDown(self) -> None:
        pass

    def test_batch(self):
        print("test_batch")

if __name__ == '__main__':
    main()
