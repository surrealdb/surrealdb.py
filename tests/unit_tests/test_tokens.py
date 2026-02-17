import pytest

from surrealdb.types import Tokens, parse_auth_result


def test_parse_auth_result_string() -> None:
    result = parse_auth_result("eyJhbGciOiJIUzI1NiJ9.xxx.yyy")
    assert isinstance(result, Tokens)
    assert result.access == "eyJhbGciOiJIUzI1NiJ9.xxx.yyy"
    assert result.refresh is None


def test_parse_auth_result_dict_access_only() -> None:
    result = parse_auth_result({"access": "jwt-token"})
    assert isinstance(result, Tokens)
    assert result.access == "jwt-token"
    assert result.refresh is None


def test_parse_auth_result_dict_access_and_refresh() -> None:
    result = parse_auth_result(
        {"access": "jwt-token", "refresh": "surreal-refresh-abc"},
    )
    assert isinstance(result, Tokens)
    assert result.access == "jwt-token"
    assert result.refresh == "surreal-refresh-abc"


def test_parse_auth_result_dict_refresh_only() -> None:
    result = parse_auth_result({"refresh": "surreal-refresh-xyz"})
    assert isinstance(result, Tokens)
    assert result.access is None
    assert result.refresh == "surreal-refresh-xyz"


def test_parse_auth_result_empty_dict() -> None:
    result = parse_auth_result({})
    assert isinstance(result, Tokens)
    assert result.access is None
    assert result.refresh is None


def test_parse_auth_result_unexpected_type() -> None:
    result = parse_auth_result(123)
    assert isinstance(result, Tokens)
    assert result.access is None
    assert result.refresh is None
