import asyncio
from typing import List
from unittest import IsolatedAsyncioTestCase

from surrealdb import AsyncSurrealDB, Table
from tests.integration.connection_params import TestConnectionParams


class TestAsyncLive(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.params = TestConnectionParams()
        self.db = AsyncSurrealDB(self.params.url)

        self.queries: List[str] = []

        await self.db.connect()
        await self.db.use(self.params.namespace, self.params.database)
        await self.db.sign_in("root", "root")

    async def test_live(self):
        if self.params.protocol.lower() == "ws":
            live_id = await self.db.live(Table("users"))
            live_queue = await self.db.live_notifications(live_id)

            await self.db.query("CREATE users;")

            notification_data = await asyncio.wait_for(live_queue.get(), 10)  # Set timeout
            self.assertEqual(notification_data.get("id"), live_id)
            self.assertEqual(notification_data.get("action"), "CREATE")


