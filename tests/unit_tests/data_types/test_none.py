"""
Tests how None is serialized when being sent to the database.

Notes:
    if an option<T> is None when being returned from the database it just isn't in the object
    will have to look into schema objects for more complete serialization.
"""
from unittest import main, IsolatedAsyncioTestCase

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.record_id import RecordID


class TestAsyncWsSurrealConnectionNone(IsolatedAsyncioTestCase):

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
        await self.connection.query("DELETE person;")

    async def test_none(self):
        schema = """
            DEFINE TABLE person SCHEMAFULL TYPE NORMAL;
            DEFINE FIELD name ON person TYPE string;
            DEFINE FIELD age ON person TYPE option<int>;
        """
        await self.connection.query(schema)
        outcome = await self.connection.create(
            "person:john",
            {"name": "John", "age": None}
        )
        record_check = RecordID(table_name="person", identifier="john")
        self.assertEqual(record_check, outcome["id"])
        self.assertEqual("John", outcome["name"])
        self.assertEqual(None, outcome.get("age"))

        outcome = await self.connection.create(
            "person:dave",
            {"name": "Dave", "age": 34}
        )
        record_check = RecordID(table_name="person", identifier="dave")
        self.assertEqual(record_check, outcome["id"])
        self.assertEqual("Dave", outcome["name"])
        self.assertEqual(34, outcome["age"])

        outcome = await self.connection.query("SELECT * FROM person")
        self.assertEqual(2, len(outcome))

        await self.connection.query("DELETE person;")
        await self.connection.close()

if __name__ == "__main__":
    main()
