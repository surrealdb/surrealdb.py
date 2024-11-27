"""
Handles the integration tests for logging into the database using blocking operations.
"""

from unittest import TestCase, main

from surrealdb import SurrealDB
from surrealdb.errors import SurrealDbError
from tests.integration.connection_params import TestConnectionParams


class TestAuth(TestCase):
    def setUp(self):
        self.params = TestConnectionParams()
        self.db = SurrealDB(self.params.url)

        self.db.connect()
        self.db.use(self.params.namespace, self.params.database)

    def tearDown(self):
        self.db.close()

    def login(self, username: str, password: str) -> None:
        self.db.sign_in(username, password)

    def test_login_success(self):
        self.login("root", "root")

    def test_login_wrong_password(self):
        with self.assertRaises(SurrealDbError) as context:
            self.login("root", "wrong")

        self.assertEqual(True, "There was a problem with authentication" in str(context.exception))

    def test_login_wrong_username(self):
        with self.assertRaises(SurrealDbError) as context:
            self.login("wrong", "root")

        self.assertEqual(True, "There was a problem with authentication" in str(context.exception))


if __name__ == "__main__":
    main()
