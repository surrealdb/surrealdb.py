import unittest
from unittest import main, IsolatedAsyncioTestCase
from surrealdb.data.types.duration import Duration, UNITS

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
import sys


class TestDurationClass(unittest.TestCase):
    """Test the Duration class functionality (synchronous)."""

    def test_parse_ms(self):
        d = Duration.parse("2ms")  # parse 2 as seconds
        self.assertEqual(d.elapsed, 2 * UNITS["ms"])

    def test_parse_int_seconds(self):
        d = Duration.parse(2)  # parse 2 as seconds
        self.assertEqual(d.elapsed, 2 * UNITS["s"])

    def test_parse_str_hours(self):
        d = Duration.parse("3h")
        self.assertEqual(d.elapsed, 3 * UNITS["h"])

    def test_parse_str_days(self):
        d = Duration.parse("2d")
        self.assertEqual(d.elapsed, 2 * UNITS["d"])

    def test_parse_unknown_unit(self):
        with self.assertRaises(ValueError):
            Duration.parse("10x")

    def test_parse_wrong_type(self):
        with self.assertRaises(TypeError):
            Duration.parse(1.5)  # float not allowed

    def test_get_seconds_and_nano(self):
        # Suppose we have 1 second + 500 nanoseconds
        d = Duration( (1 * UNITS["s"]) + 500 )
        sec, nano = d.get_seconds_and_nano()
        self.assertEqual(sec, 1)
        self.assertEqual(nano, 500)

    def test_equality(self):
        d1 = Duration.parse("2h")
        d2 = Duration.parse("2h")
        d3 = Duration.parse("3h")
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, d3)

    def test_properties(self):
        d = Duration.parse("2h")  # 7200 seconds
        self.assertEqual(d.hours, 2)
        self.assertEqual(d.minutes, 120)
        self.assertEqual(d.seconds, 7200)
        self.assertEqual(d.milliseconds, 7200 * 1000)
        self.assertEqual(d.microseconds, 7200 * 1000000)
        self.assertEqual(d.nanoseconds, 7200 * 1000000000)

    def test_to_string(self):
        d = Duration.parse("90m")  # 90 minutes = 1 hour 30 min
        # The largest integer-based unit is 1 hour so the method returns "1h"
        self.assertEqual(d.to_string(), "1h")

    def test_to_compact(self):
        d = Duration.parse(60)  # 60 seconds
        self.assertEqual(d.to_compact(), [60])


class TestAsyncWsSurrealConnectionDuration(IsolatedAsyncioTestCase):
    """
    Uses SurrealDB to create a table with a duration field, insert some data,
    and verify we can query it back without causing 'list index out of range'.
    """

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
        await self.connection.query("DELETE duration_tests;")

    async def asyncTearDown(self):
        await self.connection.query("DELETE duration_tests;")
        await self.connection.close()

    async def test_duration_int_insert(self):
        """
        Insert an integer as a duration. SurrealDB might store it so that the
        local decode sees only one item, or a different structure. If the code
        expects two items, it might trigger 'list index out of range'.
        """
        test_duration = Duration.parse("3h")

        test_outcome = await self.connection.query(
            "CREATE duration_tests:test set duration = $duration;",
            params={"duration": test_duration}
        )
        duration = test_outcome[0]["duration"]
        self.assertIsInstance(duration, Duration)
        self.assertEqual(duration.elapsed, 10800000000000)


if __name__ == "__main__":
    main()
