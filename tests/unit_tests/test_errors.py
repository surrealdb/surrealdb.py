from typing import Any

import pytest

from surrealdb.errors import SurrealDBMethodError


def test_surrealdb_method_error_init() -> None:
    """Test SurrealDBMethodError initialization."""
    error = SurrealDBMethodError("Test error message")
    assert error.message == "Test error message"


def test_surrealdb_method_error_str() -> None:
    """Test SurrealDBMethodError string representation."""
    error = SurrealDBMethodError("Test error message")
    assert str(error) == "Test error message"


def test_surrealdb_method_error_inheritance() -> None:
    """Test that SurrealDBMethodError inherits from Exception."""
    error = SurrealDBMethodError("Test error message")
    assert isinstance(error, Exception)
