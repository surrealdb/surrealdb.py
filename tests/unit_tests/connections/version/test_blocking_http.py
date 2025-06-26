from unittest import TestCase, main

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection


class TestAsyncWsSurrealConnection(TestCase):
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
        self.connection = BlockingHttpSurrealConnection(self.url)
        _ = self.connection.signin(self.vars_params)
        _ = self.connection.use(namespace=self.namespace, database=self.database_name)

    def test_version(self):
        self.assertEqual(str, type(self.connection.version()))


if __name__ == "__main__":
    main()
