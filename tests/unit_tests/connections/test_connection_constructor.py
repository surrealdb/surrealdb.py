from typing import Any

import pytest

from surrealdb import (
    AsyncHttpSurrealConnection,
    AsyncSurreal,
    AsyncWsSurrealConnection,
    BlockingHttpSurrealConnection,
    BlockingWsSurrealConnection,
    Surreal,
)


@pytest.fixture
def test_data() -> dict[str, list[str]]:
    return {
        "urls": [
            "http://localhost:5000",
            "https://localhost:5000",
            "http://localhost:5000/",
            "https://localhost:5000/",
            "ws://localhost:5000",
            "wss://localhost:5000",
            "ws://localhost:5000/",
            "wss://localhost:5000/",
        ],
        "schemes": ["http", "https", "http", "https", "ws", "wss", "ws", "wss"],
    }


def test_blocking___init__(test_data: dict[str, list[str]]) -> None:
    outcome = Surreal("ws://localhost:5000")
    assert type(outcome) == BlockingWsSurrealConnection
    outcome = Surreal("http://localhost:5000")
    assert type(outcome) == BlockingHttpSurrealConnection


def test_async___init__(test_data: dict[str, list[str]]) -> None:
    outcome = AsyncSurreal("ws://localhost:5000")
    assert type(outcome) == AsyncWsSurrealConnection
    outcome = AsyncSurreal("http://localhost:5000")
    assert type(outcome) == AsyncHttpSurrealConnection
