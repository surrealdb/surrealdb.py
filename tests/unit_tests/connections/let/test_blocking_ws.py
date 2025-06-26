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
        self.connection.query("DELETE person;")

    def tearDown(self):
        self.connection.query("DELETE person;")
        if self.connection.socket:
            self.connection.socket.close()

    def test_let(self):
        outcome = self.connection.let(
            "name",
            {
                "first": "Tobie",
                "last": "Morgan Hitchcock",
            },
        )
        self.assertIsNone(outcome)

        self.connection.query("CREATE person SET name = $name")
        outcome = self.connection.query(
            "SELECT * FROM person WHERE name.first = $name.first"
        )
        self.assertEqual(
            {"first": "Tobie", "last": "Morgan Hitchcock"}, outcome[0]["name"]
        )


if __name__ == "__main__":
    main()
