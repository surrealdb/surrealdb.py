"""A TCP proxy in front of the test server, so a test can cut the connection.

Closing the client's socket from inside the SDK would test the SDK against
itself. Cutting the TCP connection underneath it is what a network drop or a
server restart looks like from the client, and the server sees the same: the
connection, and with it every session and live query on it, is gone.
"""

import contextlib
import socket
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from tests.unit_tests.connections.conftest import PROBE_HOST, SERVER_PORT


class DroppableProxy:
    """Forwards connections to the server until told to drop or refuse them."""

    def __init__(self, upstream: tuple[str, int]) -> None:
        self._upstream = upstream
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port: int = self._listener.getsockname()[1]
        self._lock = threading.Lock()
        self._open: list[socket.socket] = []
        self._refusing = False
        self._stopped = False
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    @property
    def ws_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    def drop(self) -> None:
        """Cut every connection open through the proxy."""
        with self._lock:
            sockets, self._open = self._open, []
        for sock in sockets:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                sock.close()

    def refuse(self) -> None:
        """Close new connections as soon as they arrive, as a server that is down."""
        self._refusing = True

    def accept(self) -> None:
        self._refusing = False

    def close(self) -> None:
        self._stopped = True
        self.drop()
        with contextlib.suppress(OSError):
            self._listener.close()

    def _accept(self) -> None:
        while not self._stopped:
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            if self._refusing:
                client.close()
                continue
            try:
                server = socket.create_connection(self._upstream)
            except OSError:
                client.close()
                continue
            with self._lock:
                self._open += [client, server]
            for source, sink in ((client, server), (server, client)):
                threading.Thread(
                    target=self._pump, args=(source, sink), daemon=True
                ).start()

    def _pump(self, source: socket.socket, sink: socket.socket) -> None:
        try:
            while data := source.recv(65536):
                sink.sendall(data)
        except OSError:
            pass
        finally:
            for sock in (source, sink):
                with contextlib.suppress(OSError):
                    sock.shutdown(socket.SHUT_RDWR)


@pytest.fixture
def proxy() -> Iterator[DroppableProxy]:
    instance = DroppableProxy((PROBE_HOST, SERVER_PORT))
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture
def credentials(connection_params: dict[str, Any]) -> dict[str, Any]:
    return dict(connection_params["vars_params"])
