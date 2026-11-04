"""The async export, import and health check report a timeout as the SDK's own.

aiohttp raises ``asyncio.TimeoutError`` when its total timeout runs out. That
is the builtin ``TimeoutError`` only from Python 3.11 on, so catching the
builtin let the timeout escape as a bare ``asyncio.TimeoutError`` on 3.10,
outside the ``SurrealError`` tree.
"""

import http.server
import threading
import time
from collections.abc import Iterator

import pytest

from surrealdb.connections.health import acheck_health
from surrealdb.connections.import_export import (
    ExportOptions,
    aexport_sql,
    aimport_sql,
)
from surrealdb.connections.url import Url
from surrealdb.errors import TransportTimeoutError


class _Silent(http.server.BaseHTTPRequestHandler):
    """Takes the request and says nothing for longer than any test waits."""

    def _stall(self) -> None:
        time.sleep(3)

    def do_GET(self) -> None:
        self._stall()

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._stall()

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def silent_url() -> Iterator[Url]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Silent)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield Url(f"http://127.0.0.1:{server.server_address[1]}")
    finally:
        server.shutdown()
        server.server_close()


async def test_an_async_export_that_times_out_raises_transport_timeout(
    silent_url: Url,
) -> None:
    with pytest.raises(TransportTimeoutError):
        await aexport_sql(silent_url, ExportOptions(), 0.2, None, None, None)


async def test_an_async_import_that_times_out_raises_transport_timeout(
    silent_url: Url,
) -> None:
    with pytest.raises(TransportTimeoutError):
        await aimport_sql(silent_url, "OPTION IMPORT;", 0.2, None, None, None)


async def test_an_async_health_check_that_times_out_raises_transport_timeout(
    silent_url: Url,
) -> None:
    with pytest.raises(TransportTimeoutError):
        await acheck_health(silent_url, 0.2)
