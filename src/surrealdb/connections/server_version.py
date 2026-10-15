"""The server version a remote connection learns when it connects."""

import logging
from typing import Any

from surrealdb.errors import (
    ConnectionUnavailableError,
    UnavailableFeatureError,
    UnsupportedVersionError,
)
from surrealdb.features import (
    MAXIMUM_VERSION,
    MINIMUM_VERSION,
    Feature,
    Features,
    is_version_supported,
    parse_version,
)

logger = logging.getLogger(__name__)


class ServerVersionMixin:
    """Version handshake state shared by the remote transports.

    The transport sends a ``version`` request as the first thing on a new
    connection and passes the answer to :meth:`_adopt_server_version`.
    """

    _server_version: str | None = None
    _version_learned: bool = False
    _version_check: bool = True

    @property
    def server_version(self) -> str | None:
        """The version the server reported, such as ``"3.3.4"``.

        ``None`` until the connection has opened.
        """
        return self._server_version

    def _adopt_server_version(self, reported: Any) -> None:
        """Record the server's answer to ``version``, refusing an unsupported one.

        An answer that cannot be read as a version is recorded as unknown
        rather than refused: nothing can be gated on it, but a server build
        with an unusual version string should not be locked out by the SDK.
        """
        self._version_learned = False
        text = str(reported).strip()
        if text.startswith("surrealdb-"):
            text = text[len("surrealdb-") :]
        if parse_version(text) is None:
            logger.debug("could not read a version from %r", reported)
            self._server_version = None
            self._version_learned = True
            return
        if self._version_check and not is_version_supported(text):
            raise UnsupportedVersionError(text, MINIMUM_VERSION, MAXIMUM_VERSION)
        self._server_version = text
        self._version_learned = True

    def _forget_server_version(self) -> None:
        self._server_version = None
        self._version_learned = False

    def is_feature_supported(self, feature: Feature) -> bool:
        """Whether the connected server offers *feature*.

        Needs the version the server reported on connecting, so call it after
        the connection has opened - after ``connect()``, or after any request.
        A server whose version could not be read is assumed to support
        everything.

        :raises ConnectionUnavailableError: before the connection has opened.
        """
        if not self._version_learned:
            raise ConnectionUnavailableError(
                "the server version is not known until the connection has "
                "opened; call connect() first"
            )
        if self._server_version is None:
            return True
        return feature.supports(self._server_version)

    def _version_allows_streaming(self) -> bool:
        """Whether ``query_stream`` is worth trying on this server."""
        version = self._server_version
        return version is None or Features.QUERY_STREAMING.supports(version)

    def _require(self, feature: Feature) -> None:
        """Refuse *feature* before sending anything if the server lacks it."""
        version = self._server_version
        if version is None or feature.supports(version):
            return
        raise UnavailableFeatureError(feature.name, version, feature.since)
