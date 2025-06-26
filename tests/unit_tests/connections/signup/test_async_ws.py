from unittest import IsolatedAsyncioTestCase, TestCase, main

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


class TestAsyncWsSurrealConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.url = "ws://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.connection = AsyncWsSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )
        _ = await self.connection.query("DELETE user;")
        _ = await self.connection.query("REMOVE TABLE user;")
        _ = await self.connection.query(
            "DEFINE TABLE user SCHEMAFULL PERMISSIONS FOR select, update, delete WHERE id = $auth.id;"
            "DEFINE FIELD name ON user TYPE string;"
            "DEFINE FIELD email ON user TYPE string ASSERT string::is::email($value);"
            "DEFINE FIELD password ON user TYPE string;"
            "DEFINE FIELD enabled ON user TYPE bool;"
            "DEFINE INDEX email ON user FIELDS email UNIQUE;"
        )
        _ = await self.connection.query(
            "DEFINE ACCESS user ON DATABASE TYPE RECORD "
            "SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) "
            "SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );"
        )

    async def test_signup(self):
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
        connection = AsyncWsSurrealConnection(self.url)
        response = await connection.signup(vars)
        self.assertIsNotNone(response)

        outcome = await connection.info()
        self.assertEqual(outcome["email"], "test@gmail.com")
        self.assertEqual(outcome["name"], "test")

        await self.connection.query("DELETE user;")
        await self.connection.query("REMOVE TABLE user;")


if __name__ == "__main__":
    main()
