from unittest import TestCase, main

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


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
        self.connection = BlockingWsSurrealConnection(self.url)
        _ = self.connection.signin(self.vars_params)
        _ = self.connection.use(namespace=self.namespace, database=self.database_name)
        _ = self.connection.query("DELETE user;")
        _ = self.connection.query("REMOVE TABLE user;")
        _ = self.connection.query(
            "DEFINE TABLE user SCHEMAFULL PERMISSIONS FOR select, update, delete WHERE id = $auth.id;"
            "DEFINE FIELD name ON user TYPE string;"
            "DEFINE FIELD email ON user TYPE string ASSERT string::is::email($value);"
            "DEFINE FIELD password ON user TYPE string;"
            "DEFINE FIELD enabled ON user TYPE bool;"
            "DEFINE INDEX email ON user FIELDS email UNIQUE;"
        )
        _ = self.connection.query(
            "DEFINE ACCESS user ON DATABASE TYPE RECORD "
            "SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) "
            "SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );"
        )

    def test_signup(self):
        vars = {
            "namespace": self.namespace,
            "database": self.database_name,
            "access": "user",
            "variables": {
                "email": "test@gmail.com",
                "password": "test",
                "name": "test",
            },
        }
        connection = BlockingWsSurrealConnection(self.url)
        response = connection.signup(vars)
        self.assertIsNotNone(response)

        outcome = connection.info()
        self.assertEqual(outcome["email"], "test@gmail.com")
        self.assertEqual(outcome["name"], "test")

        self.connection.query("DELETE user;")
        self.connection.query("REMOVE TABLE user;")


if __name__ == "__main__":
    main()
