import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection


@pytest.fixture(autouse=True)
def setup_blocking_http_signin() -> None:
    """Setup fixture for blocking HTTP signin tests"""
    url = "http://localhost:8000"
    password = "root"
    username = "root"
    database_name = "test_db"
    namespace = "test_ns"
    vars_params = {
        "username": username,
        "password": password,
    }
    connection = BlockingHttpSurrealConnection(url)
    _ = connection.signin(vars_params)
    _ = connection.use(namespace=namespace, database=database_name)
    _ = connection.query("DELETE user;")
    _ = connection.query("REMOVE TABLE user;")
    _ = connection.query(
        "DEFINE TABLE user SCHEMAFULL PERMISSIONS FOR select, update, delete WHERE id = $auth.id;"
        "DEFINE FIELD name ON user TYPE string;"
        "DEFINE FIELD email ON user TYPE string;"
        "DEFINE FIELD password ON user TYPE string;"
        "DEFINE FIELD enabled ON user TYPE bool;"
        "DEFINE INDEX email ON user FIELDS email UNIQUE;"
    )
    _ = connection.query(
        "DEFINE ACCESS user ON DATABASE TYPE RECORD "
        "SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) "
        "SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );"
    )
    _ = connection.query(
        'DEFINE USER test ON NAMESPACE PASSWORD "test" ROLES OWNER; '
        'DEFINE USER test ON DATABASE PASSWORD "test" ROLES OWNER;'
    )
    _ = connection.query(
        "CREATE user SET name = 'test', email = 'test@gmail.com', password = crypto::argon2::generate('test'), enabled = true"
    )

    yield {
        "url": url,
        "password": password,
        "username": username,
        "database_name": database_name,
        "namespace": namespace,
        "vars_params": vars_params,
        "connection": connection,
    }

    connection.query("DELETE user;")
    connection.query("REMOVE TABLE user;")


def test_signin_root(setup_blocking_http_signin) -> None:
    connection = BlockingHttpSurrealConnection(setup_blocking_http_signin["url"])
    response = connection.signin(setup_blocking_http_signin["vars_params"])
    assert response is not None


def test_signin_namespace(setup_blocking_http_signin) -> None:
    connection = BlockingHttpSurrealConnection(setup_blocking_http_signin["url"])
    vars = {
        "namespace": setup_blocking_http_signin["namespace"],
        "username": "test",
        "password": "test",
    }
    response = connection.signin(vars)
    assert response is not None


def test_signin_database(setup_blocking_http_signin) -> None:
    connection = BlockingHttpSurrealConnection(setup_blocking_http_signin["url"])
    vars = {
        "namespace": setup_blocking_http_signin["namespace"],
        "database": setup_blocking_http_signin["database_name"],
        "username": "test",
        "password": "test",
    }
    response = connection.signin(vars)
    assert response is not None


def test_signin_record(setup_blocking_http_signin) -> None:
    vars = {
        "namespace": setup_blocking_http_signin["namespace"],
        "database": setup_blocking_http_signin["database_name"],
        "access": "user",
        "variables": {"email": "test@gmail.com", "password": "test"},
    }
    connection = BlockingHttpSurrealConnection(setup_blocking_http_signin["url"])
    response = connection.signin(vars)
    assert response is not None

    outcome = connection.info()
    assert outcome["email"] == "test@gmail.com"
    assert outcome["name"] == "test"
