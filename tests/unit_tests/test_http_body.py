"""A blocking HTTP body cut short of its declared length is an error.

urllib3 2 checks the length itself, but urllib3 1.26 - which the declared
``requests`` floor still allows - ends the body quietly where the connection
did, so a truncated export used to be saved as if it were complete.
"""

import http.server
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import requests

from surrealdb.connections.http_body import read_body

BODY = b"OPTION IMPORT;\n-- the whole body\n"


class _Body(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        if self.path == "/whole":
            self.wfile.write(BODY)
            return
        self.wfile.write(BODY[:10])
        self.wfile.flush()
        self.close_connection = True
        self.connection.shutdown(socket.SHUT_RDWR)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def server_url() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Body)
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("timeout", [None, 5.0], ids=["no deadline", "deadline"])
def test_a_body_cut_short_is_an_error(server_url: str, timeout: float | None) -> None:
    deadline = None if timeout is None else time.monotonic() + timeout
    with (
        requests.get(f"{server_url}/short", stream=True, timeout=5) as response,
        pytest.raises(requests.exceptions.RequestException),
    ):
        read_body(response, deadline)


@pytest.mark.parametrize("timeout", [None, 5.0], ids=["no deadline", "deadline"])
def test_a_whole_body_is_read(server_url: str, timeout: float | None) -> None:
    deadline = None if timeout is None else time.monotonic() + timeout
    with requests.get(f"{server_url}/whole", stream=True, timeout=5) as response:
        assert read_body(response, deadline) == BODY
