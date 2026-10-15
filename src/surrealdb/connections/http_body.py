"""Reading a blocking HTTP reply against a deadline.

requests' timeout bounds each wait on the socket, not the whole exchange, so a
reply that keeps trickling in can run on long past it. These read the body
with every wait cut to the time that is left.
"""

import socket
import time
from collections.abc import Iterator

import requests
import urllib3

_CHUNK = 1 << 16


def _socket(raw: object) -> socket.socket | None:
    """The socket *raw* reads from, wherever urllib3 keeps it.

    A connection that will close hands its socket to the response, leaving
    ``connection.sock`` empty, so the reply's own file is checked too.
    """
    sock = getattr(getattr(raw, "connection", None), "sock", None)
    if isinstance(sock, socket.socket):
        return sock
    fp = getattr(getattr(raw, "_fp", None), "fp", None)
    sock = getattr(getattr(fp, "raw", None), "_sock", None)
    return sock if isinstance(sock, socket.socket) else None


def iter_body(response: requests.Response, deadline: float | None) -> Iterator[bytes]:
    """The body of *response* as it arrives, unless *deadline* passes first.

    :raises TimeoutError: at the deadline.
    :raises requests.exceptions.ConnectionError: if the connection breaks.
    """
    if deadline is None:
        yield from response.iter_content(_CHUNK)
        return
    raw = response.raw
    read1 = getattr(raw, "read1", None)
    sock = _socket(raw)
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("the reply was still arriving at the deadline")
            if sock is not None:
                sock.settimeout(remaining)
            if read1 is not None:
                chunk: bytes = read1(_CHUNK, decode_content=True)
            else:
                chunk = raw.read(1 << 12, decode_content=True)
            if not chunk:
                return
            yield chunk
    except urllib3.exceptions.ReadTimeoutError as exc:
        raise TimeoutError(str(exc)) from exc
    except urllib3.exceptions.HTTPError as exc:
        raise requests.exceptions.ConnectionError(str(exc)) from exc


def read_body(response: requests.Response, deadline: float | None) -> bytes:
    """The whole body of *response*, unless *deadline* passes first."""
    if deadline is None:
        return response.content
    return b"".join(iter_body(response, deadline))
