from unittest import TestCase, main

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


class TestHttpSurrealConnection(TestCase):
    def setUp(self):
        self.url = "http://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.data = {
            "username": self.username,
            "password": self.password,
        }
        self.insert_bulk_data = [
            {
                "name": "Tobie",
            },
            {"name": "Jaime"},
        ]
        self.insert_data = [
            {
                "name": "Tobie",
            }
        ]
        self.connection = BlockingHttpSurrealConnection(self.url)
        self.connection.signin(self.vars_params)
        self.connection.use(namespace=self.namespace, database=self.database_name)
        self.connection.query("DELETE user;")

    def test_info(self):
        outcome = self.connection.info()
        # TODO => confirm that the info is what we expect

    def test_insert_string_with_data(self):
        outcome = self.connection.insert("user", self.insert_bulk_data)
        self.assertEqual(2, len(outcome))
        self.assertEqual(len(self.connection.query("SELECT * FROM user;")), 2)
        self.connection.query("DELETE user;")

    def test_insert_record_id_result_error(self):
        record_id = RecordID("user", "tobie")

        with self.assertRaises(Exception) as context:
            _ = self.connection.insert(record_id, self.insert_data)
        e = str(context.exception)
        self.assertEqual(
            "There was a problem with the database: Can not execute INSERT statement using value"
            in e
            and "user:tobie" in e,
            True,
        )
        self.connection.query("DELETE user;")


if __name__ == "__main__":
    main()
