import pytest


def test_version(blocking_http_connection):
    assert str == type(blocking_http_connection.version())
