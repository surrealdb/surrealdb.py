from unittest import TestCase, main

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID


class TestBlockingWsSurrealConnection(TestCase):
    def setUp(self):
        self.queries = ["DELETE user;"]
        self.url = "ws://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.connection = BlockingWsSurrealConnection(self.url)
        self.connection.signin(self.vars_params)
        self.connection.use(namespace=self.namespace, database=self.database_name)

    def tearDown(self):
        self.connection.query("DELETE user;")
        if self.connection.socket:
            self.connection.socket.close()

    def test_query(self):
        self.connection.query("DELETE user;")
        self.assertEqual(
            self.connection.query("CREATE user:tobie SET name = 'Tobie';"),
            [
                {
                    "id": RecordID(table_name="user", identifier="tobie"),
                    "name": "Tobie",
                }
            ],
        )
        self.assertEqual(
            self.connection.query("CREATE user:jaime SET name = 'Jaime';"),
            [
                {
                    "id": RecordID(table_name="user", identifier="jaime"),
                    "name": "Jaime",
                }
            ],
        )
        self.assertEqual(
            self.connection.query("SELECT * FROM user;"),
            [
                {
                    "id": RecordID(table_name="user", identifier="jaime"),
                    "name": "Jaime",
                },
                {
                    "id": RecordID(table_name="user", identifier="tobie"),
                    "name": "Tobie",
                },
            ],
        )
        self.connection.query("DELETE user;")


if __name__ == "__main__":
    main()
