from unittest import TestCase, main

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID


class TestblockingHttpSurrealConnection(TestCase):
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
        self.connection = BlockingHttpSurrealConnection(self.url)
        _ = self.connection.signin(self.vars_params)
        _ = self.connection.use(namespace=self.namespace, database=self.database_name)
        self.connection.query("DELETE user;")
        self.connection.query("DELETE likes;")
        self.connection.query("CREATE user:jaime SET name = 'Jaime';")
        self.connection.query("CREATE user:tobie SET name = 'Tobie';")

    def check_outcome(self, outcome: list):
        self.assertEqual(RecordID("user", "tobie"), outcome[0]["in"])
        self.assertEqual(RecordID("likes", 123), outcome[0]["out"])
        self.assertEqual(RecordID("user", "jaime"), outcome[1]["in"])
        self.assertEqual(RecordID("likes", 400), outcome[1]["out"])

    def test_insert_relation_record_ids(self):
        data = [
            {
                "in": RecordID("user", "tobie"),
                "out": RecordID("likes", 123),
            },
            {
                "in": RecordID("user", "jaime"),
                "out": RecordID("likes", 400),
            },
        ]
        outcome = self.connection.insert_relation("likes", data)
        self.assertEqual(RecordID("user", "tobie"), outcome[0]["in"])
        self.assertEqual(RecordID("likes", 123), outcome[0]["out"])
        self.assertEqual(RecordID("user", "jaime"), outcome[1]["in"])
        self.assertEqual(RecordID("likes", 400), outcome[1]["out"])
        self.connection.query("DELETE user;")
        self.connection.query("DELETE likes;")

    def test_insert_relation_record_id(self):
        data = {
            "in": RecordID("user", "tobie"),
            "out": RecordID("likes", 123),
        }
        outcome = self.connection.insert_relation("likes", data)
        self.assertEqual(RecordID("user", "tobie"), outcome[0]["in"])
        self.assertEqual(RecordID("likes", 123), outcome[0]["out"])
        self.connection.query("DELETE user;")
        self.connection.query("DELETE likes;")


if __name__ == "__main__":
    main()
