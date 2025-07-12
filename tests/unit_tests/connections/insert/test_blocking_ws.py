from unittest import TestCase, main

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID


class TestBlockingWsSurrealConnection(TestCase):
    def setUp(self):
        self.url = "ws://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.data = {
            "name": self.username,
            "password": self.password,
        }
        self.insert_bulk_data = [
            {
                "name": "Tobie",
                "email": "tobie@example.com",
                "enabled": True,
            },
            {
                "name": "Jaime",
                "email": "jaime@example.com",
                "enabled": True,
            },
        ]
        self.insert_data = [
            {
                "name": "Tobie",
                "email": "tobie@example.com",
                "enabled": True,
            }
        ]
        self.connection = BlockingWsSurrealConnection(self.url)
        self.connection.signin(self.vars_params)
        self.connection.use(namespace=self.namespace, database=self.database_name)
        self.connection.query("DELETE person;")

    def tearDown(self):
        self.connection.query("DELETE person;")
        if self.connection.socket:
            self.connection.socket.close()

    def test_insert_string_with_data(self):
        outcome = self.connection.insert("person", self.insert_bulk_data)
        self.assertEqual(2, len(outcome))
        self.assertEqual(len(self.connection.query("SELECT * FROM person;")), 2)

    def test_insert_record_id_result_error(self):
        record_id = RecordID("person", "tobie")

        with self.assertRaises(Exception) as context:
            _ = self.connection.insert(record_id, self.insert_data)
        e = str(context.exception)
        self.assertEqual(
            "There was a problem with the database: Can not execute INSERT statement using value"
            in e
            and "person:tobie" in e,
            True,
        )


if __name__ == "__main__":
    main()
