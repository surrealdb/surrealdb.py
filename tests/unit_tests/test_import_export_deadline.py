"""The blocking export and import timeout bounds the whole transfer."""

import http.server
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from surrealdb.connections.import_export import (
    ExportOptions,
    export_sql,
    export_sql_to,
    import_sql,
)
from surrealdb.connections.url import Url
from surrealdb.errors import TransportTimeoutError


class _Trickle(http.server.BaseHTTPRequestHandler):
    def _trickle(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", "100")
        self.end_headers()
        for _ in range(100):
            try:
                self.wfile.write(b"-")
                self.wfile.flush()
            except OSError:
                return
            time.sleep(0.05)

    def do_GET(self) -> None:
        self._trickle()

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._trickle()

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def trickling_url() -> Iterator[Url]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Trickle)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Url(f"http://127.0.0.1:{server.server_address[1]}")
    finally:
        server.shutdown()
        server.server_close()


def test_export_stops_at_the_deadline(trickling_url: Url) -> None:
    started = time.monotonic()
    with pytest.raises(TransportTimeoutError, match="within 0.5"):
        export_sql(trickling_url, ExportOptions(), 0.5, None, None, None)
    assert time.monotonic() - started < 2


def test_export_to_stops_at_the_deadline(trickling_url: Url, tmp_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(TransportTimeoutError, match="within 0.5"):
        export_sql_to(
            trickling_url,
            ExportOptions(),
            tmp_path / "out.surql",
            0.5,
            None,
            None,
            None,
        )
    assert time.monotonic() - started < 2


def test_import_stops_at_the_deadline(trickling_url: Url) -> None:
    started = time.monotonic()
    with pytest.raises(TransportTimeoutError, match="within 0.5"):
        import_sql(trickling_url, "OPTION IMPORT;", 0.5, None, None, None)
    assert time.monotonic() - started < 2
