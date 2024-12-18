from typing import List
from unittest import TestCase

from surrealdb import SurrealDB, Table
from surrealdb.asyncio_runtime import AsyncioRuntime
from tests.integration.connection_params import TestConnectionParams


class TestAsyncLive(TestCase):
    def setUp(self):
        self.params = TestConnectionParams()
        self.db = SurrealDB(self.params.url)

        self.queries: List[str] = []

        self.db.connect()
        self.db.use(self.params.namespace, self.params.database)
        self.db.sign_in("root", "root")

    def tearDown(self):
        for query in self.queries:
            self.db.query(query)
        self.db.close()

    def test_live(self):
        if self.params.protocol.lower() == "ws":
            self.queries = ["DELETE users;"]

            live_id = self.db.live(Table("users"))
            live_queue = self.db.live_notifications(live_id)

            self.db.query("CREATE users;")

            loop_manager = AsyncioRuntime()
            notification_data = loop_manager.loop.run_until_complete(live_queue.get())
            self.assertEqual(notification_data.get("id"), live_id)
            self.assertEqual(notification_data.get("action"), "CREATE")


