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
        self.record_id = RecordID(table_name="user", identifier="tobie")
        self.data = [
            {"op": "replace", "path": "/name", "value": "Jaime"},
            {"op": "replace", "path": "/age", "value": 35},
        ]
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

    def test_patch_string_with_data(self):
        outcome = self.connection.patch("user:tobie", self.data)
        self.check_change(outcome)
        outcome = self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])

    def test_patch_record_id_with_data(self):
        outcome = self.connection.patch(self.record_id, self.data)
        self.check_change(outcome)
        outcome = self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])

    def test_patch_table_with_data(self):
        table = Table("user")
        outcome = self.connection.patch(table, self.data)
        self.check_change(outcome[0])
        outcome = self.connection.query("SELECT * FROM user;")
        self.check_change(outcome[0])


if __name__ == "__main__":
    main()
