"""
Handles the integration tests for logging into the database using blocking operations.
"""

import os
from unittest import TestCase, main

from surrealdb import SurrealDB
from surrealdb.errors import SurrealDbError
from tests.integration.connection_params import TestConnectionParams


class TestAuth(TestCase):
    def setUp(self):
        self.params = TestConnectionParams()
        self.db = SurrealDB(self.params.url)

    def tearDown(self):
        pass

    def login(self, username: str, password: str) -> None:
        self.db.sign_in(
            {
                "username": username,
                "password": password,
            }
        )

    def test_login_success(self):
        self.login("root", "root")

    def test_login_wrong_password(self):
        with self.assertRaises(SurrealDbError) as context:
            self.login("root", "wrong")

        if os.environ.get("CONNECTION_PROTOCOL", "http") == "http":
            self.assertEqual(True, "(401 Unauthorized)" in str(context.exception))
        else:
            self.assertEqual(
                '"There was a problem with authentication"', str(context.exception)
            )

    def test_login_wrong_username(self):
        with self.assertRaises(SurrealDbError) as context:
            self.login("wrong", "root")

        if os.environ.get("CONNECTION_PROTOCOL", "http") == "http":
            self.assertEqual(True, "(401 Unauthorized)" in str(context.exception))
        else:
            self.assertEqual(
                '"There was a problem with authentication"', str(context.exception)
            )


if __name__ == "__main__":
    main()
