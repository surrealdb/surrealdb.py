from unittest import main, IsolatedAsyncioTestCase

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.datetime import DatetimeWrapper, IsoDateTimeWrapper


class TestAsyncWsSurrealConnectionDatetime(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.url = "ws://localhost:8000/rpc"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.connection = AsyncWsSurrealConnection(self.url)

        # Sign in and select DB
        await self.connection.signin(self.vars_params)
        await self.connection.use(namespace=self.namespace, database=self.database_name)

        # Cleanup
        await self.connection.query("DELETE datetime_tests;")

    async def test_datetime_wrapper(self):
        now = DatetimeWrapper.now()
        await self.connection.query(
            "CREATE datetime_tests:compact_test SET datetime = $compact_datetime;",
            params={"compact_datetime": now}
        )
        compact_test_outcome = await self.connection.query("SELECT * FROM datetime_tests;")
        self.assertEqual(
            type(compact_test_outcome[0]["datetime"]),
            DatetimeWrapper
        )

        # assert that the datetime returned from the DB is the same as the one serialized
        outcome = compact_test_outcome[0]["datetime"]
        self.assertEqual(now.dt.isoformat(), outcome.dt.isoformat() + "+00:00")

        await self.connection.query("DELETE datetime_tests;")
        await self.connection.close()

    async def test_datetime_formats(self):
        iso_datetime = "2025-02-03T12:30:45.123456Z"  # ISO 8601 datetime
        date = IsoDateTimeWrapper(iso_datetime)

        # Insert records with different datetime formats
        await self.connection.query(
            "CREATE datetime_tests:iso_tests SET datetime = $iso_datetime;",
            params={"iso_datetime": date}
        )
        compact_test_outcome = await self.connection.query("SELECT * FROM datetime_tests;")
        self.assertEqual(
            type(compact_test_outcome[0]["datetime"]),
            DatetimeWrapper
        )

        # assert that the datetime returned from the DB is the same as the one serialized
        date = compact_test_outcome[0]["datetime"].dt.isoformat()
        self.assertEqual(date + "Z", iso_datetime)

        # Cleanup
        await self.connection.query("DELETE datetime_tests;")
        await self.connection.socket.close()


if __name__ == "__main__":
    main()
