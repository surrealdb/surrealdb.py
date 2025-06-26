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
        self.connection.query("DELETE user;")
        self.connection.query("DELETE users;")
        if self.connection.socket:
            self.connection.socket.close()

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


if __name__ == "__main__":
    main()
