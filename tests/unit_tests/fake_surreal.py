"""In-process stand-ins for a SurrealDB server's RPC endpoints.

The reconnect and auth tests under ``tests/unit_tests/connections`` need a
real server. These fakes need nothing: each runs on its own thread, so blocking
and async connections can both be pointed at them, and each answers any method
however a test scripts it. The websocket one can also cut every socket, refuse
new ones for a while and push live notifications.
"""

import asyncio
import base64
import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from surrealdb.data.cbor import decode, encode


class RpcFailure(Exception):
    """Raised by a handler to answer its request with an RPC error."""

    def __init__(
        self, message: str, kind: str = "Internal", details: Any = None
    ) -> None:
        super().__init__(message)
        self.payload: dict[str, Any] = {
            "code": -32000,
            "kind": kind,
            "message": message,
        }
        if details is not None:
            self.payload["details"] = details


def token_expired() -> RpcFailure:
    """The error SurrealDB 3 gives for an access token that has expired."""
    return RpcFailure(
        "The token has expired",
        kind="NotAllowed",
        details={"kind": "Auth", "details": {"kind": "TokenExpired"}},
    )


def jwt(subject: str = "root", lifetime: float = 3600.0, **claims: Any) -> str:
    """A token the SDK can read the expiry and identity of; never verified."""

    def part(value: dict[str, Any]) -> str:
        raw = json.dumps(value).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    now = time.time()
    body = {"iat": now, "exp": now + lifetime, "ID": subject, "jti": uuid.uuid4().hex}
    body.update(claims)
    return f"{part({'alg': 'none'})}.{part(body)}.signature"


@dataclass
class Call:
    """One request the fake received."""

    socket: int
    method: str
    params: Any
    session: Any
    token: str | None = None
    content_type: str | None = None


Handler = Callable[[Call], Any]


class _Scripted:
    """What both fakes share: the calls they saw and how they answer them."""

    def __init__(self, version: str) -> None:
        self.version = version
        self.calls: list[Call] = []
        self.handlers: dict[str, Handler] = {}

    def respond(self, method: str, handler: Handler) -> None:
        """Answer *method* with ``handler(call)``; raise RpcFailure to refuse."""
        self.handlers[method] = handler

    def methods(self, socket: int | None = None) -> list[str]:
        return [c.method for c in self.calls if socket is None or c.socket == socket]

    def calls_to(self, method: str, socket: int | None = None) -> list[Call]:
        return [
            c
            for c in self.calls
            if c.method == method and (socket is None or c.socket == socket)
        ]

    def wait_for(self, predicate: Callable[[], bool], timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > deadline:
                raise AssertionError(f"timed out; calls were {self.methods()}")
            time.sleep(0.01)

    def default(self, call: Call) -> Any:
        if call.method == "version":
            return self.version
        if call.method in ("signin", "signup"):
            return jwt()
        if call.method == "refresh":
            return {"access": jwt(), "refresh": f"refresh-{uuid.uuid4().hex}"}
        if call.method in ("live", "begin"):
            return uuid.uuid4()
        if call.method == "query":
            return [{"status": "OK", "result": [], "time": "0ms"}]
        return None

    def _answer(
        self,
        raw: bytes,
        socket: int,
        token: str | None = None,
        content_type: str | None = None,
    ) -> bytes:
        request = decode(raw)
        call = Call(
            socket,
            request["method"],
            request.get("params"),
            request.get("session"),
            token,
            content_type,
        )
        self.calls.append(call)
        handler = self.handlers.get(call.method, self.default)
        reply: dict[str, Any] = {"id": request["id"]}
        try:
            reply["result"] = handler(call)
        except RpcFailure as failure:
            reply["error"] = failure.payload
        return encode(reply)


class FakeSurreal(_Scripted):
    """A fake server speaking plain ``cbor`` on ``ws://127.0.0.1:<port>/rpc``."""

    def __init__(self, version: str = "surrealdb-3.0.0") -> None:
        super().__init__(version)
        self.accepting = True
        self._sockets: list[ServerConnection] = []
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._server: Server | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(5)
        assert self._server is not None
        self.port: int = self._server.sockets[0].getsockname()[1]

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    @property
    def sockets_opened(self) -> int:
        return len(self._sockets)

    def drop(self) -> None:
        """Cut every open socket at once, as a network failure would."""
        self._call(self._drop())

    def notify(self, live_id: Any, action: str = "CREATE", record: Any = None) -> None:
        """Push a live notification on the newest socket."""
        frame = {"result": {"id": live_id, "action": action, "result": record}}
        self._call(self._sockets[-1].send(encode(frame)))

    def close(self) -> None:
        if self._server is not None:
            self._call(self._stop())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(5)

    def _call(self, coroutine: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(5)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start())
        self._ready.set()
        self._loop.run_forever()

    async def _start(self) -> None:
        self._server = await serve(
            self._handle,
            "127.0.0.1",
            0,
            subprotocols=["cbor"],  # type: ignore[list-item]
            process_request=self._gate,
        )

    async def _stop(self) -> None:
        assert self._server is not None
        self._server.close()
        await self._server.wait_closed()

    def _gate(self, connection: ServerConnection, request: Request) -> Response | None:
        if self.accepting:
            return None
        return connection.respond(HTTPStatus.SERVICE_UNAVAILABLE, "down\n")

    async def _drop(self) -> None:
        for socket in self._sockets:
            socket.transport.abort()

    async def _handle(self, socket: ServerConnection) -> None:
        index = len(self._sockets)
        self._sockets.append(socket)
        try:
            async for raw in socket:
                frame = raw if isinstance(raw, bytes) else raw.encode()
                await socket.send(self._answer(frame, index))
        except ConnectionClosed:
            pass


class _HttpServer(ThreadingHTTPServer):
    # Room for every request a test sends at once: past the default backlog of
    # five, the kernel resets the connections it has no room for.
    request_queue_size = 64
    daemon_threads = True


class FakeSurrealHttp(_Scripted):
    """A fake server answering ``POST /rpc`` in plain ``cbor``.

    Each call's ``token`` is the bearer token the request carried, if any, and
    its ``content_type`` the format the request was sent in.
    """

    def __init__(self, version: str = "surrealdb-3.0.0") -> None:
        super().__init__(version)
        fake = self
        # A proxy in front of the server: a status to answer a call with in
        # plain text instead of passing it on, or None to pass it on.
        self.proxy: Callable[[Call], int | None] = lambda call: None

        class _Rpc(BaseHTTPRequestHandler):
            # Kept alive: the blocking client reads its body in a way an
            # HTTP/1.0 server, closing after each reply, does not survive.
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                bearer = self.headers.get("Authorization", "")
                token = bearer.removeprefix("Bearer ") or None
                kind = self.headers.get("Content-Type")
                reply = fake._answer(body, 0, token, kind)
                status = fake.proxy(fake.calls[-1])
                if status is not None:
                    text = b"refused by the proxy"
                    self.send_response(status)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(text)))
                    self.end_headers()
                    self.wfile.write(text)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/cbor")
                self.send_header("Content-Length", str(len(reply)))
                self.end_headers()
                self.wfile.write(reply)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self._server = _HttpServer(("127.0.0.1", 0), _Rpc)
        self.port: int = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, args=(0.01,), daemon=True
        )
        self._thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(5)
