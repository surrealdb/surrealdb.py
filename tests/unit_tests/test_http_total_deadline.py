"""The blocking HTTP timeout bounds the whole reply, not each wait for a byte."""

import http.server
import threading
import time
from collections.abc import Iterator

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.errors import TransportTimeoutError


class _Trickle(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.send_header("Content-Type", "application/cbor")
        self.send_header("Content-Length", "100")
        self.end_headers()
        for _ in range(100):
            try:
                self.wfile.write(b"\xa0")
                self.wfile.flush()
            except OSError:
                return
            time.sleep(0.05)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def trickling_url() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Trickle)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def test_a_reply_that_trickles_in_still_times_out(trickling_url: str) -> None:
    db = BlockingHttpSurrealConnection(trickling_url, timeout=0.5)
    started = time.monotonic()
    with pytest.raises(TransportTimeoutError):
        db.query("RETURN 1").execute()
    assert time.monotonic() - started < 3
