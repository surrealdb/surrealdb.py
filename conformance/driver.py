"""The surrealdb-protocol conformance driver for this SDK.

The runner in surrealdb-protocol (``conformance/runner/cli.ts``) starts this
process once per scenario and transport, and talks to it in JSON lines on
stdin and stdout: ``{"id": 1, "op": "query", "args": {...}}`` in, and
``{"id": 1, "ok": true, "result": ...}`` or
``{"id": 1, "ok": false, "error": {"kind": ...}}`` out. Every op goes through
the SDK's public async API; an op it has no API for answers ``Unsupported``,
which the runner reports as a skip. See ``conformance/README.md``.
"""

import asyncio
import contextlib
import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.typed_json import to_json, to_native
from surrealdb import AsyncSurreal, ExportOptions, Table
from surrealdb.errors import (
    HttpStatusError,
    ImportFailedError,
    ServerError,
    UnsupportedFeatureError,
)
from surrealdb.streaming import DoneFrame, ErrorFrame, ValueFrame

OPS = [
    "connect",
    "close",
    "version",
    "signin",
    "signup",
    "authenticate",
    "invalidate",
    "info",
    "use",
    "set",
    "unset",
    "query",
    "query_stream",
    "run",
    "live",
    "live_of",
    "live_id",
    "next_notification",
    "kill",
    "new_session",
    "fork_session",
    "list_sessions",
    "close_session",
    "begin",
    "commit",
    "cancel",
    "import",
    "export",
]


class DriverError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def unsupported(what: str) -> DriverError:
    return DriverError("Unsupported", f"surrealdb.py has no API for {what}")


def error_info(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, DriverError):
        return {"kind": exc.kind, "message": str(exc)}
    if isinstance(exc, UnsupportedFeatureError):
        return {"kind": "Unsupported", "message": str(exc)}
    if isinstance(exc, ImportFailedError):
        return {
            "kind": "Query",
            "message": str(exc),
            "failures": [error_info(f) for f in exc.failures],
        }
    if isinstance(exc, ServerError):
        info: dict[str, Any] = {"kind": exc.kind, "message": str(exc)}
        if exc.details is not None:
            info["details"] = to_json(exc.details)
        if exc.code:
            info["code"] = exc.code
        return info
    if isinstance(exc, HttpStatusError):
        status = exc.status
        kind = {401: "NotAllowed", 403: "NotAllowed", 404: "NotFound"}.get(
            status, "Validation"
        )
        return {"kind": kind, "message": str(exc)}
    return {"kind": "Internal", "message": f"{type(exc).__name__}: {exc}"}


def auth_params(wire: dict[str, Any], *, signup: bool) -> dict[str, Any]:
    """The runner's wire keys (``user``, ``pass``, ``ns``, ``db``, ``ac``) as the SDK's.

    With ``user`` it is a system user, with ``key`` bearer access, and
    otherwise record access, where every key but ``ns``, ``db`` and ``ac`` is
    a variable. Signup is record access only.
    """
    rest = dict(wire)
    params: dict[str, Any] = {}
    for short, long in (("ns", "namespace"), ("db", "database"), ("ac", "access")):
        if short in rest:
            params[long] = rest.pop(short)
    if not signup and "user" in rest:
        params["username"] = rest.pop("user")
        if "pass" in rest:
            params["password"] = rest.pop("pass")
    elif not signup and "key" in rest:
        params["key"] = rest.pop("key")
    if rest:
        params["variables"] = rest
    return params


class Subscription:
    def __init__(self, live: Any, session: str | None) -> None:
        self.live = live
        self.session = session
        self.queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.killed = False
        self.task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        with contextlib.suppress(Exception):
            async for notification in self.live:
                await self.queue.put(notification)
        await self.queue.put(None)


class Driver:
    def __init__(self) -> None:
        self.db: Any = None
        self.transport = "ws"
        self.sessions: dict[str, Any] = {}
        self.txns: dict[str, tuple[Any, str | None]] = {}
        self.subs: dict[str, Subscription] = {}
        self.selected: dict[str | None, dict[str, Any]] = {}
        self.next_handle = 1

    def session(self, handle: Any) -> Any:
        if handle is None:
            return self.db
        try:
            return self.sessions[handle]
        except KeyError:
            raise DriverError("NotFound", f"no session {handle}") from None

    def scope(self, args: dict[str, Any]) -> Any:
        txn = args.get("txn")
        if txn is None:
            return self.session(args.get("session"))
        found = self.txns.get(txn)
        if found is None or found[1] != args.get("session"):
            raise DriverError(
                "NotFound", f"no transaction {txn} in session {args.get('session')}"
            )
        return found[0]

    def session_only(self, op: str, args: dict[str, Any]) -> Any:
        if args.get("txn") is not None:
            raise unsupported(f"{op} in a transaction")
        return self.session(args.get("session"))

    def handle(self, prefix: str) -> str:
        handle = f"{prefix}-{self.next_handle}"
        self.next_handle += 1
        return handle

    async def shutdown(self) -> None:
        for sub in self.subs.values():
            sub.task.cancel()
        if self.db is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.db.close(), 1)

    async def query(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        vars = to_native(args.get("vars") or {})
        results: dict[int, dict[str, Any]] = {}
        async for frame in self.scope(args).query(args["sql"], vars).stream():
            if isinstance(frame, ErrorFrame):
                results[frame.index] = {"ok": False, "error": error_info(frame.error)}
            elif isinstance(frame, DoneFrame):
                results[frame.index] = {
                    "ok": True,
                    "result": to_json(frame.result.value),
                }
            elif not isinstance(frame, ValueFrame):
                raise DriverError("Internal", f"unexpected frame {frame!r}")
        return [results[i] for i in sorted(results)]

    async def call(self, op: str, args: dict[str, Any]) -> Any:
        if op == "connect":
            await self.shutdown()
            self.sessions.clear()
            self.txns.clear()
            self.subs.clear()
            self.selected.clear()
            self.transport = args["transport"]
            self.db = AsyncSurreal(args["url"], reconnect=False, version_check=False)
            await self.db.connect()
            return None
        if op == "close":
            await self.db.close()
            return None
        if op == "version":
            return await self.db.version()
        if op in ("signin", "signup"):
            target = self.session_only(op, args)
            credentials = auth_params(
                to_native(args["credentials"]), signup=op == "signup"
            )
            tokens = await (
                target.signin(credentials)
                if op == "signin"
                else target.signup(credentials)
            )
            return to_json(getattr(tokens, "access", tokens))
        if op == "authenticate":
            await self.session_only(op, args).authenticate(to_native(args["token"]))
            return None
        if op == "invalidate":
            await self.session_only(op, args).invalidate()
            return None
        if op == "info":
            return to_json(await self.session_only(op, args).info())
        if op == "use":
            target = self.session_only(op, args)
            await target.use(args.get("namespace"), args.get("database"))
            selected = self.selected.setdefault(
                args.get("session"), {"namespace": None, "database": None}
            )
            for key in ("namespace", "database"):
                if key in args:
                    selected[key] = args[key]
            return dict(selected)
        if op == "set":
            await self.scope(args).set(args["name"], to_native(args["value"]))
            return None
        if op == "unset":
            await self.scope(args).unset(args["name"])
            return None
        if op in ("query", "query_stream"):
            return await self.query(args)
        if op == "run":
            fn_args = [to_native(a) for a in args.get("args") or []]
            return to_json(
                await self.scope(args).run(args["name"], fn_args, args.get("version"))
            )
        if op == "live":
            live = await self.session_only(op, args).live(
                Table(args["table"]), args.get("diff", False)
            )
            return self.subscribe(live, args.get("session"))
        if op == "live_of":
            live = self.session_only(op, args).live_of(to_native(args["id"]))
            return self.subscribe(live, args.get("session"))
        if op == "live_id":
            return to_json(UUID(str(self.sub(args).live)))
        if op == "next_notification":
            sub = self.sub(args)
            try:
                message = await asyncio.wait_for(
                    sub.queue.get(), args.get("timeout", 5000) / 1000
                )
            except asyncio.TimeoutError:
                return None
            if message is None:
                sub.queue.put_nowait(None)
                if sub.killed:
                    await asyncio.sleep(args.get("timeout", 5000) / 1000)
                    return None
                return {"action": "KILLED"}
            return {
                "action": message.get("action"),
                "record": to_json(message.get("record")),
                "result": to_json(message.get("result")),
            }
        if op == "kill":
            sub = self.sub(args)
            if args.get("txn") is not None or args.get("session") != sub.session:
                raise unsupported("kill outside the subscription's own session")
            await sub.live.kill()
            sub.killed = True
            return None
        if op == "new_session":
            return self.keep(await self.db.new_session())
        if op == "fork_session":
            source = args.get("from")
            session_id = None if source is None else self.session(source).id
            return self.keep(await self.db.fork_session(session_id))
        if op == "list_sessions":
            return [str(s) for s in await self.db.sessions()]
        if op == "close_session":
            await self.session_only(op, args).close_session()
            self.sessions.pop(args["session"], None)
            return None
        if op == "begin":
            target = self.session_only(op, args)
            if not hasattr(target, "begin_transaction"):
                raise unsupported(f"transactions over {self.transport}")
            handle = self.handle("txn")
            txn = await target.begin_transaction()
            self.txns[handle] = (txn, args.get("session"))
            return handle
        if op in ("commit", "cancel"):
            txn = self.scope(args)
            await (txn.commit() if op == "commit" else txn.cancel())
            return None
        if op == "import":
            if args.get("session") is not None or args.get("txn") is not None:
                raise unsupported("import in a session or transaction")
            await self.db.import_(args["surql"])
            return None
        if op == "export":
            if args.get("session") is not None or args.get("txn") is not None:
                raise unsupported("export in a session or transaction")
            options = args.get("options")
            return await self.db.export(ExportOptions(**options) if options else None)
        raise unsupported(op)

    def subscribe(self, live: Any, session: str | None) -> str:
        handle = self.handle("live")
        self.subs[handle] = Subscription(live, session)
        return handle

    def sub(self, args: dict[str, Any]) -> Subscription:
        try:
            return self.subs[args["subscription"]]
        except KeyError:
            raise DriverError("NotFound", "no such subscription") from None

    def keep(self, session: Any) -> str:
        handle = str(session.id)
        self.sessions[handle] = session
        return handle


def _sdk_version() -> str:
    try:
        return version("surrealdb")
    except PackageNotFoundError:
        return "unknown"


async def main() -> None:
    driver = Driver()
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )

    def write(message: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

    while line := await reader.readline():
        if not line.strip():
            continue
        request = json.loads(line)
        request_id, op, args = request["id"], request["op"], request.get("args") or {}
        if op == "hello":
            result = {"name": "surrealdb.py", "version": _sdk_version(), "ops": OPS}
            write({"id": request_id, "ok": True, "result": result})
            continue
        try:
            write({"id": request_id, "ok": True, "result": await driver.call(op, args)})
        except Exception as exc:
            write({"id": request_id, "ok": False, "error": error_info(exc)})
    await driver.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
