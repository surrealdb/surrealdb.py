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

    def test_unset(self):
        self.connection.query("DELETE person;")
        outcome = self.connection.let(
            "name",
            {
                "first": "Tobie",
                "last": "Morgan Hitchcock",
            },
        )
        self.assertEqual(None, outcome)
        self.connection.query("CREATE person SET name = $name")
        outcome = self.connection.query(
            "SELECT * FROM person WHERE name.first = $name.first"
        )
        self.assertEqual(1, len(outcome))
        self.assertEqual(
            {"first": "Tobie", "last": "Morgan Hitchcock"}, outcome[0]["name"]
        )

        self.connection.unset(key="name")

        # because the key was unset then $name.first is None returning []
        outcome = self.connection.query(
            "SELECT * FROM person WHERE name.first = $name.first"
        )
        self.assertEqual([], outcome)

        self.connection.query("DELETE person;")


if __name__ == "__main__":
    main()
