"""``vars`` takes any ``Mapping``, not only a ``dict``.

The SDK only reads the variables a caller passes, so a ``TypedDict`` or a
read-only mapping is as good as a ``dict``. These tests pin that every
connection accepts one, puts it on the wire as the plain map the encoder needs,
and leaves the caller's mapping as it was. The request is read at ``_send``, so
no server is needed.
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, TypedDict

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.cbor import decode
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod

SQL = "SELECT * FROM person WHERE age > $age AND name = $name"


class Params(TypedDict):
    age: int
    name: str


class Credentials(TypedDict):
    username: str
    password: str


def _typed_params() -> Mapping[str, Any]:
    return Params(age=18, name="Tobie")


def _proxied_params() -> Mapping[str, Any]:
    return MappingProxyType({"age": 18, "name": "Tobie"})


MAPPINGS = [
    pytest.param(_typed_params, id="typeddict"),
    pytest.param(_proxied_params, id="mappingproxy"),
]


def _async_connection(kind: str) -> tuple[Any, dict[str, Any]]:
    conn: Any
    if kind == "ws":
        conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc", streaming=False)
    else:
        conn = AsyncHttpSurrealConnection("http://localhost:8000")
    store: dict[str, Any] = {}

    async def fake_send(
        message: RequestMessage, process: str, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        store["message"] = message
        return {"result": []}

    conn._send = fake_send
    return conn, store


def _blocking_connection(kind: str) -> tuple[Any, dict[str, Any]]:
    conn: Any
    if kind == "ws":
        conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc", streaming=False)
    else:
        conn = BlockingHttpSurrealConnection("http://localhost:8000")
    store: dict[str, Any] = {}

    def fake_send(
        message: RequestMessage, process: str, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        store["message"] = message
        return {"result": []}

    conn._send = fake_send
    return conn, store


def _wire_params(message: RequestMessage) -> Any:
    return decode(message.encoded())["params"]


def _assert_plain_dict_sent(message: RequestMessage, key: str) -> None:
    assert type(message.kwargs[key]) is dict


@pytest.mark.parametrize("kind", ["ws", "http"])
@pytest.mark.parametrize("make", MAPPINGS)
async def test_async_query_accepts_a_mapping(
    kind: str, make: Callable[[], Mapping[str, Any]]
) -> None:
    conn, store = _async_connection(kind)
    given = make()

    await conn.query(SQL, given)

    message = store["message"]
    assert message.method == RequestMethod.QUERY
    _assert_plain_dict_sent(message, "params")
    assert _wire_params(message) == [SQL, {"age": 18, "name": "Tobie"}]


@pytest.mark.parametrize("kind", ["ws", "http"])
@pytest.mark.parametrize("make", MAPPINGS)
def test_blocking_query_accepts_a_mapping(
    kind: str, make: Callable[[], Mapping[str, Any]]
) -> None:
    conn, store = _blocking_connection(kind)
    given = make()

    conn.query(SQL, given).execute()

    message = store["message"]
    assert message.method == RequestMethod.QUERY
    _assert_plain_dict_sent(message, "params")
    assert _wire_params(message) == [SQL, {"age": 18, "name": "Tobie"}]


@pytest.mark.parametrize("kind", ["ws", "http"])
@pytest.mark.parametrize("make", MAPPINGS)
async def test_async_query_raw_accepts_a_mapping(
    kind: str, make: Callable[[], Mapping[str, Any]]
) -> None:
    conn, store = _async_connection(kind)

    await conn.query_raw(SQL, make())

    message = store["message"]
    _assert_plain_dict_sent(message, "params")
    assert message.kwargs["params"] == {"age": 18, "name": "Tobie"}


@pytest.mark.parametrize("kind", ["ws", "http"])
@pytest.mark.parametrize("make", MAPPINGS)
def test_blocking_query_raw_accepts_a_mapping(
    kind: str, make: Callable[[], Mapping[str, Any]]
) -> None:
    conn, store = _blocking_connection(kind)

    conn.query_raw(SQL, make())

    message = store["message"]
    _assert_plain_dict_sent(message, "params")
    assert message.kwargs["params"] == {"age": 18, "name": "Tobie"}


@pytest.mark.parametrize("kind", ["ws", "http"])
async def test_async_signin_and_signup_accept_a_mapping(kind: str) -> None:
    conn, store = _async_connection(kind)
    credentials = Credentials(username="root", password="root")

    await conn.signin(credentials)
    signin = store["message"]
    await conn.signup(MappingProxyType(dict(credentials)))
    signup = store["message"]

    _assert_plain_dict_sent(signin, "params")
    assert _wire_params(signin) == [{"user": "root", "pass": "root"}]
    _assert_plain_dict_sent(signup, "data")
    assert signup.kwargs["data"] == dict(credentials)


@pytest.mark.parametrize("kind", ["ws", "http"])
def test_blocking_signin_and_signup_accept_a_mapping(kind: str) -> None:
    conn, store = _blocking_connection(kind)
    credentials = Credentials(username="root", password="root")

    conn.signin(credentials)
    signin = store["message"]
    conn.signup(MappingProxyType(dict(credentials)))
    signup = store["message"]

    _assert_plain_dict_sent(signin, "params")
    assert _wire_params(signin) == [{"user": "root", "pass": "root"}]
    _assert_plain_dict_sent(signup, "data")
    assert signup.kwargs["data"] == dict(credentials)


def test_the_callers_mapping_is_not_the_one_sent() -> None:
    conn, store = _blocking_connection("ws")
    given = {"age": 18, "name": "Tobie"}

    conn.query_raw(SQL, given)

    sent = store["message"].kwargs["params"]
    assert sent == given
    assert sent is not given
    given["age"] = 99
    assert sent["age"] == 18


def test_a_batch_accepts_a_mapping() -> None:
    conn, store = _blocking_connection("ws")
    conn.batch().query(SQL, _typed_params()).query(
        "RETURN $age", MappingProxyType({"age": 18})
    ).execute()

    sent = store["message"].kwargs["params"]
    assert sent == {"age": 18, "name": "Tobie"}
