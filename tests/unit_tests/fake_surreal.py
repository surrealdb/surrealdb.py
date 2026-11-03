"""An in-process stand-in for a SurrealDB server's websocket RPC endpoint.

The reconnect tests under ``tests/unit_tests/connections/reconnect`` need a
real server. This fake needs nothing: it runs on its own thread and event loop,
so blocking and async connections can both be pointed at it, and it can cut
every socket, refuse new ones for a while, push live notifications and answer
any method however a test scripts it.
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


Handler = Callable[[Call], Any]


class FakeSurreal:
    """A fake server speaking plain ``cbor`` on ``ws://127.0.0.1:<port>/rpc``."""

    def __init__(self, version: str = "surrealdb-3.0.0") -> None:
        self.version = version
        self.calls: list[Call] = []
        self.handlers: dict[str, Handler] = {}
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

    def wait_for(self, predicate: Callable[[], bool], timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > deadline:
                raise AssertionError(f"timed out; calls were {self.methods()}")
            time.sleep(0.01)

    def close(self) -> None:
        if self._server is not None:
            self._call(self._stop())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(5)

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
                request = decode(raw if isinstance(raw, bytes) else raw.encode())
                params = request.get("params")
                call = Call(index, request["method"], params, request.get("session"))
                self.calls.append(call)
                handler = self.handlers.get(call.method, self.default)
                reply: dict[str, Any] = {"id": request["id"]}
                try:
                    reply["result"] = handler(call)
                except RpcFailure as failure:
                    reply["error"] = failure.payload
                await socket.send(encode(reply))
        except ConnectionClosed:
            pass
