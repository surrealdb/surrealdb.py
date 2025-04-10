import decimal
from unittest import main, IsolatedAsyncioTestCase
from surrealdb.connections.async_ws import AsyncWsSurrealConnection


class TestAsyncWsSurrealConnectionNumeric(IsolatedAsyncioTestCase):

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

        # Cleanup any existing data
        await self.connection.query("DELETE numeric_tests;")

    async def test_dec_literal(self):
        """
        Test storing and retrieving a literal decimal using SurrealDB's 'dec' suffix directly in SurrealQL.
        """
        await self.connection.query("CREATE numeric_tests:literal_test SET value = 99.99dec;")

        result = await self.connection.query("SELECT * FROM numeric_tests;")
        stored_value = result[0]["value"]

        self.assertEqual(str(stored_value), "99.99")
        self.assertIsInstance(stored_value, decimal.Decimal)

        await self.connection.query("DELETE numeric_tests;")

    async def test_float_parameter(self):
        """Test storing and retrieving a Python float value."""
        float_value = 3.141592653589793

        # Insert the float value via parameterized query
        initial_result = await self.connection.query(
            "CREATE numeric_tests:float_test SET value = $float_val;",
            params={"float_val": float_value}
        )
        self.assertIsInstance(initial_result[0]["value"], float)
        self.assertEqual(initial_result[0]["value"], 3.141592653589793)

        # Retrieve the record
        second_result = await self.connection.query("SELECT * FROM numeric_tests;")
        self.assertIsInstance(second_result[0]["value"], float)
        self.assertEqual(second_result[0]["value"], 3.141592653589793)

        # Cleanup
        await self.connection.query("DELETE numeric_tests;")

    async def asyncTearDown(self):
        await self.connection.close()


if __name__ == "__main__":
    main()
