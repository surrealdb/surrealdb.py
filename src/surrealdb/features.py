"""Which SurrealDB versions this SDK supports, and what each one can do.

A connection asks the server for its version as soon as it connects. A server
outside ``MINIMUM_VERSION`` (inclusive) to ``MAXIMUM_VERSION`` (exclusive) is
refused with :class:`~surrealdb.errors.UnsupportedVersionError` unless the
connection was built with ``version_check=False``. Features that need a newer
server than the minimum are listed in :class:`Features`; using one against an
older server raises :class:`~surrealdb.errors.UnavailableFeatureError` before
anything is sent, and ``db.is_feature_supported(Features.SESSIONS)`` asks first.

Versions are compared on major, minor and patch only, so a pre-release or
nightly build counts as the release it leads up to: ``3.4.0-nightly`` supports
everything ``3.4.0`` does, and ``5.0.0-alpha.1`` is outside the range.
"""

import re
from dataclasses import dataclass

MINIMUM_VERSION = "2.0.0"
MAXIMUM_VERSION = "5.0.0"

_VERSION = re.compile(r"^(?:surrealdb-)?v?(\d+)\.(\d+)\.(\d+)")


def parse_version(version: str) -> tuple[int, int, int] | None:
    """Read ``(major, minor, patch)`` from a version string, or ``None``.

    Accepts what the ``version`` RPC returns (``surrealdb-3.3.4``), a bare
    ``3.3.4``, and anything carrying a pre-release or build suffix after it.
    """
    match = _VERSION.match(version.strip())
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _require_version(version: str) -> tuple[int, int, int]:
    parsed = parse_version(version)
    if parsed is None:
        raise ValueError(
            f"{version!r} is not a SurrealDB version; expected something like "
            "'3.3.4' or 'surrealdb-3.3.4'"
        )
    return parsed


def is_version_supported(
    version: str,
    minimum: str = MINIMUM_VERSION,
    until: str | None = MAXIMUM_VERSION,
) -> bool:
    """Whether *version* is at least *minimum* and below *until*.

    ``until=None`` sets no upper bound.
    """
    parsed = _require_version(version)
    if parsed < _require_version(minimum):
        return False
    return until is None or parsed < _require_version(until)


@dataclass(frozen=True)
class Feature:
    """Something a server only offers from (or until) a given version."""

    name: str
    since: str | None = None
    until: str | None = None

    def supports(self, version: str) -> bool:
        """Whether a server reporting *version* offers this feature.

        A feature with no ``until`` has no upper bound, so it stays available
        on a server newer than the SDK knows when ``version_check=False``.
        """
        return is_version_supported(version, self.since or MINIMUM_VERSION, self.until)

    def __str__(self) -> str:
        return self.name


class Features:
    """The features gated on the server version. Named as in the JS SDK."""

    LIVE_QUERIES = Feature("live-queries")
    SESSIONS = Feature("sessions", "3.0.0")
    API = Feature("api", "3.0.0")
    REFRESH_TOKENS = Feature("refresh-tokens", "3.0.0")
    TRANSACTIONS = Feature("transactions", "3.0.0")
    IMPORT_FAILURE_REPORTING = Feature("import-failure-reporting", "3.1.0")
    QUERY_STREAMING = Feature("query-streaming", "3.3.0")


__all__ = [
    "MAXIMUM_VERSION",
    "MINIMUM_VERSION",
    "Feature",
    "Features",
    "is_version_supported",
    "parse_version",
]
