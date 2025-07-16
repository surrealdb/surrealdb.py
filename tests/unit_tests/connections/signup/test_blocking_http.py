import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


@pytest.fixture(autouse=True)
def setup_blocking_http_signup():
    """Setup fixture for blocking HTTP signup tests"""
    url = "http://localhost:8000"
    password = "root"
    username = "root"
    vars_params = {
        "username": username,
        "password": password,
    }
    database_name = "test_db"
    namespace = "test_ns"
    connection = BlockingHttpSurrealConnection(url)
    _ = connection.signin(vars_params)
    _ = connection.use(namespace=namespace, database=database_name)
    _ = connection.query("DELETE user;")
    _ = connection.query("REMOVE TABLE user;")
    _ = connection.query(
        "DEFINE TABLE user SCHEMAFULL PERMISSIONS FOR select, update, delete WHERE id = $auth.id;"
        "DEFINE FIELD name ON user TYPE string;"
        "DEFINE FIELD email ON user TYPE string ASSERT string::is::email($value);"
        "DEFINE FIELD password ON user TYPE string;"
        "DEFINE FIELD enabled ON user TYPE bool;"
        "DEFINE INDEX email ON user FIELDS email UNIQUE;"
    )
    _ = connection.query(
        "DEFINE ACCESS user ON DATABASE TYPE RECORD "
        "SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) "
        "SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );"
    )

    yield {
        "url": url,
        "password": password,
        "username": username,
        "vars_params": vars_params,
        "database_name": database_name,
        "namespace": namespace,
        "connection": connection,
    }

    connection.query("DELETE user;")
    connection.query("REMOVE TABLE user;")


def test_signup(setup_blocking_http_signup):
    vars = {
        "namespace": setup_blocking_http_signup["namespace"],
        "database": setup_blocking_http_signup["database_name"],
        "access": "user",
        "variables": {
            "email": "test@gmail.com",
            "password": "test",
            "name": "test",
        },
    }
    connection = BlockingHttpSurrealConnection(setup_blocking_http_signup["url"])
    response = connection.signup(vars)
    assert response is not None

    outcome = connection.info()
    assert outcome["email"] == "test@gmail.com"
    assert outcome["name"] == "test"
