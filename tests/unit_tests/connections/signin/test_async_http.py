from unittest import main, IsolatedAsyncioTestCase

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


class TestAsyncHttpSurrealConnection(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.url = "http://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.connection = AsyncHttpSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(namespace=self.namespace, database=self.database_name)
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
            'DEFINE ACCESS user ON DATABASE TYPE RECORD '
            'SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) '
            'SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );'
        )
        _ = await self.connection.query(
            'DEFINE USER test ON NAMESPACE PASSWORD "test" ROLES OWNER; '
            'DEFINE USER test ON DATABASE PASSWORD "test" ROLES OWNER;'
        )
        _ = await self.connection.query(
            "CREATE user SET name = 'test', email = 'test@gmail.com', password = crypto::argon2::generate('test'), enabled = true"
        )

    async def test_signin_root(self):
        connection = AsyncHttpSurrealConnection(self.url)
        outcome = await connection.signin(self.vars_params)
        self.assertIn("token", outcome)  # Check that the response contains a token

    async def test_signin_namespace(self):
        connection = AsyncHttpSurrealConnection(self.url)
        vars = {
            "namespace": self.namespace,
            "username": "test",
            "password": "test",
        }
        _ = await connection.signin(vars)
        _ = await self.connection.query("DELETE user;")
        _ = await self.connection.query("REMOVE TABLE user;")

    async def test_signin_database(self):
        connection = AsyncHttpSurrealConnection(self.url)
        vars = {
            "namespace": self.namespace,
            "database": self.database_name,
            "username": "test",
            "password": "test",
        }
        _ = await connection.signin(vars)
        _ = await self.connection.query("DELETE user;")
        _ = await self.connection.query("REMOVE TABLE user;")

    async def test_signin_record(self):
        vars = {
            "namespace": self.namespace,
            "database": self.database_name,
            "access": "user",
            "variables": {
                "email": "test@gmail.com",
                "password": "test"
            }
        }
        connection = AsyncHttpSurrealConnection(self.url)
        # for below if client is HTTP then persist and attach to all headers
        _ = await connection.signin(vars)

        outcome = await connection.info()
        self.assertEqual(outcome["email"], "test@gmail.com")
        self.assertEqual(outcome["name"], "test")

        await self.connection.query("DELETE user;")
        await self.connection.query("REMOVE TABLE user;")


if __name__ == "__main__":
    main()
