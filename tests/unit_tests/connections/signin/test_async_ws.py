import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


@pytest.fixture(autouse=True)
async def setup_async_ws_signin() -> None:
    """Setup fixture for async WS signin tests"""
    url = "ws://localhost:8000"
    password = "root"
    username = "root"
    database_name = "test_db"
    namespace = "test_ns"
    vars_params = {
        "username": username,
        "password": password,
    }
    connection = AsyncWsSurrealConnection(url)
    _ = await connection.signin(vars_params)
    _ = await connection.use(namespace=namespace, database=database_name)
    _ = await connection.query("DELETE user;")
    _ = await connection.query("REMOVE TABLE user;")
    _ = await connection.query(
        "DEFINE TABLE user SCHEMAFULL PERMISSIONS FOR select, update, delete WHERE id = $auth.id;"
        "DEFINE FIELD name ON user TYPE string;"
        "DEFINE FIELD email ON user TYPE string;"
        "DEFINE FIELD password ON user TYPE string;"
        "DEFINE FIELD enabled ON user TYPE bool;"
        "DEFINE INDEX email ON user FIELDS email UNIQUE;"
    )
    _ = await connection.query(
        "DEFINE ACCESS user ON DATABASE TYPE RECORD "
        "SIGNUP ( CREATE user SET name = $name, email = $email, password = crypto::argon2::generate($password), enabled = true ) "
        "SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) );"
    )
    _ = await connection.query(
        'DEFINE USER test ON NAMESPACE PASSWORD "test" ROLES OWNER; '
        'DEFINE USER test ON DATABASE PASSWORD "test" ROLES OWNER;'
    )
    _ = await connection.query(
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

    await connection.query("DELETE user;")
    await connection.query("REMOVE TABLE user;")


@pytest.mark.asyncio
async def test_signin_root(setup_async_ws_signin) -> None:
    connection = AsyncWsSurrealConnection(setup_async_ws_signin["url"])
    response = await connection.signin(setup_async_ws_signin["vars_params"])
    assert response is not None


@pytest.mark.asyncio
async def test_signin_namespace(setup_async_ws_signin) -> None:
    connection = AsyncWsSurrealConnection(setup_async_ws_signin["url"])
    vars = {
        "namespace": setup_async_ws_signin["namespace"],
        "username": "test",
        "password": "test",
    }
    response = await connection.signin(vars)
    assert response is not None


@pytest.mark.asyncio
async def test_signin_database(setup_async_ws_signin) -> None:
    connection = AsyncWsSurrealConnection(setup_async_ws_signin["url"])
    vars = {
        "namespace": setup_async_ws_signin["namespace"],
        "database": setup_async_ws_signin["database_name"],
        "username": "test",
        "password": "test",
    }
    response = await connection.signin(vars)
    assert response is not None


@pytest.mark.asyncio
async def test_signin_record(setup_async_ws_signin) -> None:
    vars = {
        "namespace": setup_async_ws_signin["namespace"],
        "database": setup_async_ws_signin["database_name"],
        "access": "user",
        "variables": {"email": "test@gmail.com", "password": "test"},
    }
    connection = AsyncWsSurrealConnection(setup_async_ws_signin["url"])
    response = await connection.signin(vars)
    assert response is not None

    outcome = await connection.info()
    assert outcome["email"] == "test@gmail.com"
    assert outcome["name"] == "test"
