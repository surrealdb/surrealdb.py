from unittest import TestCase, main

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


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

    def tearDown(self):
        if self.connection.socket:
            self.connection.socket.close()

    def test_version(self):
        self.assertEqual(str, type(self.connection.version()))


if __name__ == "__main__":
    main()
