import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


@pytest.fixture(autouse=True)
async def setup_schema(async_ws_connection):
    await async_ws_connection.query("DELETE user;")
    await async_ws_connection.query("REMOVE TABLE user;")
    await async_ws_connection.query(
        "DEFINE TABLE user SCHEMAFULL PERMISSIONS FOR select, update, delete WHERE id = $auth.id;"
        "DEFINE FIELD name ON user TYPE string;"
        "DEFINE FIELD email ON user TYPE string ASSERT string::is::email($value);"
        "DEFINE FIELD password ON user TYPE string;"
        "DEFINE FIELD enabled ON user TYPE bool;"
        "DEFINE INDEX email ON user FIELDS email UNIQUE;"
    )
    await async_ws_connection.query(
        "DEFINE ACCESS user ON DATABASE TYPE RECORD "
        "SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) "
        "SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );"
    )
    yield
    await async_ws_connection.query("DELETE user;")
    await async_ws_connection.query("REMOVE TABLE user;")


@pytest.mark.asyncio
async def test_signup(setup_schema):
    url = "ws://localhost:8000"
    vars = {
        "namespace": "test_ns",
        "database": "test_db",
        "access": "user",
        "variables": {
            "email": "test@gmail.com",
            "password": "test",
            "name": "test",
        },
    }
    connection = AsyncWsSurrealConnection(url)
    response = await connection.signup(vars)
    assert response is not None

    outcome = await connection.info()
    assert outcome["email"] == "test@gmail.com"
    assert outcome["name"] == "test"
