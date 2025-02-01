from unittest import main, TestCase
import os
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


class TestAsyncWsSurrealConnection(TestCase):

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
        self.main_connection = BlockingWsSurrealConnection(self.url)
        _ = self.main_connection.signin(self.vars_params)
        _ = self.main_connection.use(namespace=self.namespace, database=self.database_name)
        self.main_connection.query("DELETE user;")
        _ = self.main_connection.query_raw("CREATE user:jaime SET name = 'Jaime';")

        self.connection = BlockingWsSurrealConnection(self.url)
        _ = self.connection.signin(self.vars_params)
        _ = self.connection.use(namespace=self.namespace, database=self.database_name)

    def test_invalidate(self):
        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))
        outcome = self.main_connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))

        _ = self.connection.invalidate()

        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(0, len(outcome))
        outcome = self.main_connection.query("SELECT * FROM user;")
        self.assertEqual(1, len(outcome))

        '''
        # Exceptions are raised only when SurrealDB doesn't allow guest mode
        with self.assertRaises(Exception) as context:
            _ = self.connection.query("CREATE user:jaime SET name = 'Jaime';")
        self.assertEqual(
            "IAM error: Not enough permissions" in str(context.exception),
            True
        )
        '''

        self.main_connection.query("DELETE user;")
        self.main_connection.close()
        self.connection.close()

if __name__ == "__main__":
    main()
