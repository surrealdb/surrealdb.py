from unittest import TestCase, main

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection


class TestAsyncHttpSurrealConnection(TestCase):
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

    def test_select(self):
        self.connection.query("DELETE user;")
        self.connection.query("DELETE users;")

        self.connection.query("CREATE user:tobie SET name = 'Tobie';")
        self.connection.query("CREATE user:jaime SET name = 'Jaime';")

        self.connection.query("CREATE users:one SET name = 'one';")
        self.connection.query("CREATE users:two SET name = 'two';")

        outcome = self.connection.select("user")
        self.assertEqual(
            outcome[0]["name"],
            "Jaime",
        )
        self.assertEqual(
            outcome[1]["name"],
            "Tobie",
        )
        self.assertEqual(2, len(outcome))

        self.connection.query("DELETE user;")
        self.connection.query("DELETE users;")


if __name__ == "__main__":
    main()
