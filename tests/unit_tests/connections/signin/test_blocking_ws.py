from unittest import TestCase, main

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


class TestAsyncHttpSurrealConnection(TestCase):
    def setUp(self):
        self.url = "ws://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
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
        _ = self.connection.query(
            'DEFINE USER test ON NAMESPACE PASSWORD "test" ROLES OWNER; '
            'DEFINE USER test ON DATABASE PASSWORD "test" ROLES OWNER;'
        )
        _ = self.connection.query(
            "CREATE user SET name = 'test', email = 'test@gmail.com', password = crypto::argon2::generate('test'), enabled = true"
        )

    def test_signin_root(self):
        connection = BlockingWsSurrealConnection(self.url)
        response = connection.signin(self.vars_params)
        self.assertIsNotNone(response)
        self.connection.socket.close()
        connection.close()

    def test_signin_namespace(self):
        connection = BlockingWsSurrealConnection(self.url)
        vars = {
            "namespace": self.namespace,
            "username": "test",
            "password": "test",
        }
        response = connection.signin(vars)
        self.assertIsNotNone(response)
        _ = self.connection.query("DELETE user;")
        _ = self.connection.query("REMOVE TABLE user;")
        self.connection.socket.close()
        connection.socket.close()

    def test_signin_database(self):
        connection = BlockingWsSurrealConnection(self.url)
        vars = {
            "namespace": self.namespace,
            "database": self.database_name,
            "username": "test",
            "password": "test",
        }
        response = connection.signin(vars)
        self.assertIsNotNone(response)
        _ = self.connection.query("DELETE user;")
        _ = self.connection.query("REMOVE TABLE user;")
        self.connection.socket.close()
        connection.socket.close()

    def test_signin_record(self):
        vars = {
            "namespace": self.namespace,
            "database": self.database_name,
            "access": "user",
            "variables": {"email": "test@gmail.com", "password": "test"},
        }
        connection = BlockingWsSurrealConnection(self.url)
        response = connection.signin(vars)
        self.assertIsNotNone(response)

        outcome = connection.info()
        self.assertEqual(outcome["email"], "test@gmail.com")
        self.assertEqual(outcome["name"], "test")

        self.connection.query("DELETE user;")
        self.connection.query("REMOVE TABLE user;")
        self.connection.socket.close()
        connection.socket.close()


if __name__ == "__main__":
    main()
