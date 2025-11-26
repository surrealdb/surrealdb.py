from collections.abc import AsyncGenerator

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


@pytest.fixture(autouse=True)
async def setup_schema(
    async_http_connection: AsyncHttpSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query("REMOVE TABLE user;")
    await async_http_connection.query(
        "DEFINE TABLE user SCHEMAFULL PERMISSIONS FOR select, update, delete WHERE id = $auth.id;"
        "DEFINE FIELD name ON user TYPE string;"
        "DEFINE FIELD email ON user TYPE string;"
        "DEFINE FIELD password ON user TYPE string;"
        "DEFINE FIELD enabled ON user TYPE bool;"
        "DEFINE INDEX email ON user FIELDS email UNIQUE;"
    )
    await async_http_connection.query(
        "DEFINE ACCESS user ON DATABASE TYPE RECORD "
        "SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) "
        "SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );"
    )
    await async_http_connection.query(
        'DEFINE USER test ON NAMESPACE PASSWORD "test" ROLES OWNER; '
        'DEFINE USER test ON DATABASE PASSWORD "test" ROLES OWNER;'
    )
    await async_http_connection.query(
        "CREATE user SET name = 'test', email = 'test@gmail.com', password = crypto::argon2::generate('test'), enabled = true"
    )
    yield
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query("REMOVE TABLE user;")


@pytest.mark.asyncio
async def test_signin_root(setup_schema: None) -> None:
    url = "http://localhost:8000"
    vars_params = {
        "username": "root",
        "password": "root",
    }
    connection = AsyncHttpSurrealConnection(url)
    response = await connection.signin(vars_params)
    assert response is not None


@pytest.mark.asyncio
async def test_signin_namespace(setup_schema: None) -> None:
    url = "http://localhost:8000"
    connection = AsyncHttpSurrealConnection(url)
    vars = {
        "namespace": "test_ns",
        "username": "test",
        "password": "test",
    }
    response = await connection.signin(vars)
    assert response is not None


@pytest.mark.asyncio
async def test_signin_database(setup_schema: None) -> None:
    url = "http://localhost:8000"
    connection = AsyncHttpSurrealConnection(url)
    vars = {
        "namespace": "test_ns",
        "database": "test_db",
        "username": "test",
        "password": "test",
    }
    response = await connection.signin(vars)
    assert response is not None


@pytest.mark.asyncio
async def test_signin_record(setup_schema: None) -> None:
    url = "http://localhost:8000"
    vars = {
        "namespace": "test_ns",
        "database": "test_db",
        "access": "user",
        "variables": {"email": "test@gmail.com", "password": "test"},
    }
    connection = AsyncHttpSurrealConnection(url)
    response = await connection.signin(vars)
    assert response is not None

    outcome = await connection.info()
    assert outcome["email"] == "test@gmail.com"
    assert outcome["name"] == "test"
