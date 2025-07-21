import pytest


def test_version(blocking_ws_connection):
    assert str == type(blocking_ws_connection.version())
