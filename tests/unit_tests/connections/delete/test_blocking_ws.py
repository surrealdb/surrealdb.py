from unittest import TestCase, main

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


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
        self.data = {"name": "Jaime", "age": 35}
        self.record_id = RecordID("user", "tobie")
        self.connection = BlockingWsSurrealConnection(self.url)
        self.connection.signin(self.vars_params)
        self.connection.use(namespace=self.namespace, database=self.database_name)
        self.connection.query("DELETE user;")
        self.connection.query("CREATE user:tobie SET name = 'Tobie';")

    def tearDown(self):
        self.connection.query("DELETE user;")
        if self.connection.socket:
            self.connection.socket.close()

    def check_no_change(self, data: dict):
        self.assertEqual(self.record_id, data["id"])
        self.assertEqual("Tobie", data["name"])

    def check_change(self, data: dict):
        self.assertEqual(self.record_id, data["id"])
        self.assertEqual("Jaime", data["name"])
        self.assertEqual(35, data["age"])

    def test_delete_string(self):
        outcome = self.connection.delete("user:tobie")
        self.check_no_change(outcome)

        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(outcome, [])

    def test_delete_record_id(self):
        first_outcome = self.connection.delete(self.record_id)
        self.check_no_change(first_outcome)

        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(outcome, [])

    def test_delete_table(self):
        self.connection.query("CREATE user:jaime SET name = 'Jaime';")
        table = Table("user")

        first_outcome = self.connection.delete(table)
        self.assertEqual(2, len(first_outcome))

        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(outcome, [])


if __name__ == "__main__":
    main()
