from unittest import TestCase, main
from uuid import UUID

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data import RecordID


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
        self.connection = BlockingWsSurrealConnection(self.url)
        self.connection.signin(self.vars_params)
        self.connection.use(namespace=self.namespace, database=self.database_name)
        self.connection.query("DELETE user;")
        self.connection.query("CREATE user:tobie SET name = 'Tobie';")
        self.pub_connection = BlockingWsSurrealConnection(self.url)
        self.pub_connection.signin(self.vars_params)
        self.pub_connection.use(namespace=self.namespace, database=self.database_name)

    def tearDown(self):
        self.pub_connection.query("DELETE user;")
        if self.pub_connection.socket:
            self.pub_connection.socket.close()
        if self.connection.socket:
            self.connection.socket.close()

    def test_live_subscription(self):
        # Start the live query
        query_uuid = self.connection.live("user")
        self.assertIsInstance(query_uuid, UUID)

        # Start the live subscription
        subscription = self.connection.subscribe_live(query_uuid)

        # Push an update
        self.pub_connection.query("CREATE user:jaime SET name = 'Jaime';")

        # Wait for the live subscription update
        try:
            for update in subscription:
                self.assertEqual(update["name"], "Jaime")
                self.assertEqual(update["id"], RecordID("user", "jaime"))
                break  # Exit after receiving the first update
        except Exception as e:
            self.fail(f"Error waiting for live subscription update: {e}")

        self.pub_connection.kill(query_uuid)


if __name__ == "__main__":
    main()
