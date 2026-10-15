"""Fixtures for the reconnect tests: a proxy that can cut the connection."""

import os
from collections.abc import Iterator

import pytest

from tests.unit_tests.connections.reconnect.proxy import DroppableProxy

_UPSTREAM = (
    os.environ.get("SURREALDB_HOST", "127.0.0.1"),
    int(os.environ.get("SURREALDB_PORT", "8000")),
)


@pytest.fixture
def proxy() -> Iterator[DroppableProxy]:
    instance = DroppableProxy(_UPSTREAM)
    try:
        yield instance
    finally:
        instance.close()
