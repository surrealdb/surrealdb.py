"""Connection status and the events a connection publishes.

Named and shaped as in the JS SDK: ``db.status`` is one of ``"disconnected"``,
``"connecting"``, ``"reconnecting"`` or ``"connected"``, and
``db.subscribe(event, listener)`` registers a callback and returns the function
that removes it again::

    unsubscribe = db.subscribe("reconnecting", lambda: print("lost the server"))
    ...
    unsubscribe()

========================  ==========================================
event                     listener arguments
========================  ==========================================
``"connecting"``          none
``"connected"``           the server version, such as ``"3.3.4"``
``"reconnecting"``        none
``"disconnected"``        none
``"error"``               the exception
``"auth"``                the new :class:`~surrealdb.types.Tokens`, or
                          ``None`` once signed out; the session id
``"using"``               the namespace, the database and the session id
========================  ==========================================

The session id passed to ``"auth"`` and ``"using"`` is ``None`` for the
connection's own (root) session.

Listeners run on whichever thread or task noticed the change, so they should
return quickly. A listener on an async connection may be a coroutine function;
it is scheduled as a task rather than awaited. An exception raised by a
listener is logged and otherwise ignored, so one faulty listener cannot break
the connection or starve the others.
"""

import asyncio
import inspect
import logging
import threading
from collections.abc import Callable
from typing import Any, Literal

logger = logging.getLogger(__name__)

ConnectionStatus = Literal["disconnected", "connecting", "reconnecting", "connected"]

ConnectionEvent = Literal[
    "connecting",
    "connected",
    "reconnecting",
    "disconnected",
    "error",
    "auth",
    "using",
]

EVENTS: tuple[ConnectionEvent, ...] = (
    "connecting",
    "connected",
    "reconnecting",
    "disconnected",
    "error",
    "auth",
    "using",
)


class EventsMixin:
    """Status and listener registry shared by the connection classes."""

    _status: ConnectionStatus = "disconnected"
    # Set by `_init_events()`, which every connection calls from `__init__`.
    _listeners: dict[str, list[Callable[..., Any]]]  # pyright: ignore[reportUninitializedInstanceVariable]
    _listener_tasks: set["asyncio.Task[Any]"]  # pyright: ignore[reportUninitializedInstanceVariable]
    _listener_lock: threading.Lock  # pyright: ignore[reportUninitializedInstanceVariable]

    def _init_events(self) -> None:
        """Give this connection its own registry; call from ``__init__``."""
        self._status = "disconnected"
        self._listeners = {}
        self._listener_tasks = set()
        self._listener_lock = threading.Lock()

    @property
    def status(self) -> ConnectionStatus:
        """Where the connection is: disconnected, connecting, reconnecting or connected."""
        return self._status

    @property
    def is_connected(self) -> bool:
        """Whether the connection is open and ready for requests."""
        return self._status == "connected"

    def subscribe(
        self, event: ConnectionEvent, listener: Callable[..., Any]
    ) -> Callable[[], None]:
        """Call *listener* each time *event* happens; returns the unsubscriber."""
        if event not in EVENTS:
            raise ValueError(
                f"unknown connection event {event!r}; expected one of "
                f"{', '.join(EVENTS)}"
            )
        if not callable(listener):
            raise TypeError(f"listener must be callable, not {type(listener).__name__}")
        with self._listener_lock:
            self._listeners.setdefault(event, []).append(listener)

        def unsubscribe() -> None:
            with self._listener_lock:
                listeners = self._listeners.get(event, [])
                if listener in listeners:
                    listeners.remove(listener)

        return unsubscribe

    def _set_status(self, status: ConnectionStatus, *payload: Any) -> None:
        """Move to *status* and publish the event of the same name."""
        if status == self._status and status != "connected":
            return
        self._status = status
        self._emit(status, *payload)

    def _emit(self, event: str, *payload: Any) -> None:
        with self._listener_lock:
            listeners = list(self._listeners.get(event, ()))
        for listener in listeners:
            try:
                outcome = listener(*payload)
                if inspect.isawaitable(outcome):
                    self._schedule_listener(outcome)
            except Exception:
                logger.exception("a %r listener raised", event)

    def _schedule_listener(self, outcome: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "a connection listener returned an awaitable outside an event "
                "loop, so it was not run"
            )
            if inspect.iscoroutine(outcome):
                outcome.close()
            return
        task = loop.create_task(outcome)
        self._listener_tasks.add(task)
        task.add_done_callback(self._listener_done)

    def _listener_done(self, task: "asyncio.Task[Any]") -> None:
        self._listener_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("a connection listener raised", exc_info=task.exception())
