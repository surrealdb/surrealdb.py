from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestSignUp(TestCase):

    def setUp(self):
        self.queries = []
        self.email = "john.doe@example.com"
        self.password = "password123"
        self.namespace = "namespace"
        self.database = "database"
        self.connection = SurrealDB(Url().url)

    def tearDown(self):
        for query in self.queries:
            self.connection.query(query)

    def login(self, username: str, password: str) -> None:
        self.connection.signin(
            {
                "username": username,
                "password": password,
            }
        )

    def test_signup(self):
        self.queries.append("DELETE user_scope;")
        self.queries.append("DELETE user;")
        self.login(username="root", password="root")
        self.connection.use_namespace(self.namespace)
        self.connection.use_database(self.database)

        query_str = """
        DEFINE SCOPE user_scope SESSION 24h
        SIGNUP ( CREATE user SET email = $email, password = crypto::argon2::generate($password) )
        SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) )
        """
        self.connection.query(query_str)

        _wrapped_jwt = self.connection.signup(
            namespace=self.namespace,
            database=self.database,
            scope="user_scope", data={
            'email': self.email,
            'password': self.password
        })
        print(_wrapped_jwt)


if __name__ == "__main__":
    main()
