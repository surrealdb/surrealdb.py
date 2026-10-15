"""The supported server range and the features gated on the server version."""

import pytest

from surrealdb import MAXIMUM_VERSION, MINIMUM_VERSION, Feature, Features
from surrealdb.connections.server_version import ServerVersionMixin
from surrealdb.errors import (
    ConnectionUnavailableError,
    UnavailableFeatureError,
    UnsupportedFeatureError,
    UnsupportedVersionError,
)
from surrealdb.features import is_version_supported, parse_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("surrealdb-3.3.4", (3, 3, 4)),
        ("3.3.4", (3, 3, 4)),
        ("v2.0.5", (2, 0, 5)),
        ("3.4.0-nightly+20261014.4f7fa16", (3, 4, 0)),
        ("surrealdb-3.0.0-beta.2", (3, 0, 0)),
        ("  4.0.0\n", (4, 0, 0)),
        ("nightly", None),
        ("", None),
    ],
)
def test_parse_version(text: str, expected: tuple[int, int, int] | None) -> None:
    assert parse_version(text) == expected


def test_the_declared_range() -> None:
    assert MINIMUM_VERSION == "2.0.0"
    assert MAXIMUM_VERSION == "5.0.0"


@pytest.mark.parametrize(
    ("version", "supported"),
    [
        ("1.5.6", False),
        ("2.0.0", True),
        ("2.0.5", True),
        ("3.3.4", True),
        ("3.4.0-nightly", True),
        ("4.0.0", True),
        ("4.9.99", True),
        ("5.0.0-alpha.1", False),
        ("5.0.0", False),
    ],
)
def test_supported_range_is_minimum_inclusive_to_five_exclusive(
    version: str, supported: bool
) -> None:
    assert is_version_supported(version) is supported


def test_a_malformed_version_is_rejected_with_an_actionable_message() -> None:
    with pytest.raises(ValueError, match="not a SurrealDB version"):
        is_version_supported("latest")


@pytest.mark.parametrize(
    ("feature", "version", "supported"),
    [
        (Features.SESSIONS, "2.3.10", False),
        (Features.SESSIONS, "3.0.0-beta.2", True),
        (Features.TRANSACTIONS, "3.0.0", True),
        (Features.API, "2.6.0", False),
        (Features.REFRESH_TOKENS, "3.0.5", True),
        (Features.IMPORT_FAILURE_REPORTING, "3.0.5", False),
        (Features.IMPORT_FAILURE_REPORTING, "3.1.0", True),
        (Features.QUERY_STREAMING, "3.2.9", False),
        (Features.QUERY_STREAMING, "3.3.0", True),
        (Features.QUERY_STREAMING, "4.0.0", True),
        (Features.LIVE_QUERIES, "2.0.0", True),
    ],
)
def test_features_are_gated_like_the_js_sdk(
    feature: Feature, version: str, supported: bool
) -> None:
    assert feature.supports(version) is supported


def test_a_feature_can_have_an_upper_bound() -> None:
    retired = Feature("retired", since="2.0.0", until="3.0.0")
    assert retired.supports("2.6.0")
    assert not retired.supports("3.0.0")


class _Gate(ServerVersionMixin):
    def __init__(self, version_check: bool = True) -> None:
        self._version_check = version_check


def test_an_unsupported_server_is_refused() -> None:
    gate = _Gate()
    with pytest.raises(UnsupportedVersionError) as info:
        gate._adopt_server_version("surrealdb-5.0.0")
    assert info.value.version == "5.0.0"
    assert info.value.minimum == MINIMUM_VERSION
    assert info.value.maximum == MAXIMUM_VERSION
    assert "version_check=False" in str(info.value)
    assert gate.server_version is None


def test_version_check_false_accepts_any_server() -> None:
    gate = _Gate(version_check=False)
    gate._adopt_server_version("surrealdb-1.5.6")
    assert gate.server_version == "1.5.6"
    assert not gate.is_feature_supported(Features.SESSIONS)


def test_feature_support_needs_a_connection() -> None:
    with pytest.raises(ConnectionUnavailableError, match="connect"):
        _Gate().is_feature_supported(Features.SESSIONS)


def test_an_unreadable_version_gates_nothing() -> None:
    gate = _Gate()
    gate._adopt_server_version("some-custom-build")
    assert gate.server_version is None
    assert gate.is_feature_supported(Features.QUERY_STREAMING)
    gate._require(Features.SESSIONS)


def test_require_names_the_feature_and_both_versions() -> None:
    gate = _Gate()
    gate._adopt_server_version("surrealdb-2.3.10")
    with pytest.raises(UnavailableFeatureError) as info:
        gate._require(Features.TRANSACTIONS)
    assert isinstance(info.value, UnsupportedFeatureError)
    assert info.value.feature == "transactions"
    assert info.value.version == "2.3.10"
    assert info.value.since == "3.0.0"
    assert "3.0.0 or later" in str(info.value)
