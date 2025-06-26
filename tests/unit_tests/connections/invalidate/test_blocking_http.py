import os
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
        self.main_connection = BlockingHttpSurrealConnection(self.url)
        _ = self.main_connection.signin(self.vars_params)
        _ = self.main_connection.use(
            namespace=self.namespace, database=self.database_name
        )
        self.main_connection.query("DELETE user;")
        _ = self.main_connection.query_raw("CREATE user:jaime SET name = 'Jaime';")

        self.connection = BlockingHttpSurrealConnection(self.url)
        _ = self.connection.signin(self.vars_params)
        _ = self.connection.use(namespace=self.namespace, database=self.database_name)

    def test_run_test(self):
        if os.environ.get("NO_GUEST_MODE") == "True":
            self.invalidate_test_for_no_guest_mode()
        else:
            self.invalidate_with_guest_mode_on()

    def invalidate_test_for_no_guest_mode(self):
        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))
        outcome = self.main_connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))

        _ = self.connection.invalidate()

        try:
            outcome = self.connection.query("SELECT * FROM user;")
            self.assertEqual(0, len(outcome))
        except Exception as err:
            self.assertEqual("IAM error: Not enough permissions" in str(err), True)
        outcome = self.main_connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))

        self.main_connection.query("DELETE user;")

    def invalidate_with_guest_mode_on(self):
        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))
        outcome = self.main_connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))

        self.connection.invalidate()

        try:
            outcome = self.connection.query("SELECT * FROM user;")
            self.assertEqual(0, len(outcome))
        except Exception as err:
            self.assertEqual("IAM error: Not enough permissions" in str(err), True)

        outcome = self.main_connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))

        self.main_connection.query("DELETE user;")


if __name__ == "__main__":
    main()
