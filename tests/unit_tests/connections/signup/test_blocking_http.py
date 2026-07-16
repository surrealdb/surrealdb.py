from collections.abc import Iterator
from typing import Any

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Value


@pytest.fixture(autouse=True)
def setup_blocking_http_signup() -> Iterator[dict[str, Any]]:
    """Setup fixture for blocking HTTP signup tests"""
    url = "http://localhost:8000"
    password = "root"
    username = "root"
    vars_params: dict[str, Value] = {
        "username": username,
        "password": password,
    }
    database_name = "test_db"
    namespace = "test_ns"
    connection = BlockingHttpSurrealConnection(url)
    _ = connection.signin(vars_params)
    connection.use(namespace=namespace, database=database_name)
    _ = connection.query_raw("DELETE user;")
    _ = connection.query_raw("REMOVE TABLE user;")
    connection.query(
        "DEFINE TABLE user SCHEMAFULL PERMISSIONS FOR select, update, delete WHERE id = $auth.id;"
        "DEFINE FIELD name ON user TYPE string;"
        "DEFINE FIELD email ON user TYPE string;"
        "DEFINE FIELD password ON user TYPE string;"
        "DEFINE FIELD enabled ON user TYPE bool;"
        "DEFINE INDEX email ON user FIELDS email UNIQUE;"
    ).execute()
    _ = connection.query_raw("REMOVE ACCESS user ON DATABASE;")
    connection.query(
        "DEFINE ACCESS user ON DATABASE TYPE RECORD "
        "SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) "
        "SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );"
    ).execute()

    yield {
        "url": url,
        "password": password,
        "username": username,
        "vars_params": vars_params,
        "database_name": database_name,
        "namespace": namespace,
        "connection": connection,
    }

    connection.query("DELETE user;").execute()
    connection.query("REMOVE TABLE user;").execute()


def test_signup(setup_blocking_http_signup: dict[str, Any]) -> None:
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
