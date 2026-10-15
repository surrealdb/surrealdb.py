"""Live query subscriptions, as the JS SDK has them.

``live()`` returns a subscription that is also the live query's UUID, so code
that passes the id to ``subscribe_live()`` or ``kill()`` keeps working. The
subscription itself can be iterated for notifications, killed, and used as a
context manager that kills it on exit::

    async with await db.live("person") as people:
        async for change in people:
            print(change["action"], change["result"])

``live_of(id)`` attaches to a live query started some other way, such as a
``LIVE SELECT`` sent with ``query()``. The connection does not know that
query's definition, so unlike one from ``live()`` it is not restarted after a
reconnect.

A subscription ends cleanly when the query is killed, by this client or any
other, and when the connection closes.
"""

import weakref
from collections.abc import AsyncIterator, Container, Iterator
from types import TracebackType
from typing import Any
from uuid import UUID

from surrealdb.types import Value


class _Subscription(UUID):
    """The shared part: a UUID that also knows its connection and session."""

    __slots__ = ("_connection", "_killed", "_managed", "_session_id")

    _connection: Any  # pyright: ignore[reportUninitializedInstanceVariable]
    _session_id: UUID | None  # pyright: ignore[reportUninitializedInstanceVariable]
    _managed: bool  # pyright: ignore[reportUninitializedInstanceVariable]
    _killed: bool  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(
        self,
        live_id: str | UUID,
        connection: Any,
        session_id: UUID | None,
        managed: bool,
    ) -> None:
        super().__init__(str(live_id))
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_session_id", session_id)
        object.__setattr__(self, "_managed", managed)
        object.__setattr__(self, "_killed", False)

    @property
    def id(self) -> UUID:
        """The live query's id, as a plain UUID."""
        return UUID(int=self.int)

    @property
    def managed(self) -> bool:
        """Whether the connection started this query, and so restarts it
        after a reconnect. ``False`` for one attached with ``live_of()``."""
        return self._managed

    @property
    def is_alive(self) -> bool:
        """Whether the query is still running, as far as this client knows:
        ``False`` once it is killed - through the subscription or the
        connection - its notifications have ended, or the connection closed."""
        return not self._killed

    def _ended(self) -> None:
        object.__setattr__(self, "_killed", True)

    def __reduce__(self) -> tuple[type[UUID], tuple[str]]:
        return (UUID, (str(self),))

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class AsyncLiveSubscription(_Subscription):
    """A live query on an async connection."""

    async def __aiter__(self) -> AsyncIterator[dict[str, Value]]:
        if self._killed:
            return
        notifications = await self._connection.subscribe_live(self)
        async for notification in notifications:
            yield notification
        self._ended()

    async def kill(self) -> None:
        """Stop the live query. Iterators over it end.

        Does nothing if the query has already ended. If the request fails the
        subscription stays alive, so the kill can be tried again.
        """
        if self._killed:
            return
        await self._connection.kill(self, session_id=self._session_id)
        self._ended()

    async def __aenter__(self) -> "AsyncLiveSubscription":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.kill()


class LiveSubscription(_Subscription):
    """A live query on a blocking connection."""

    def __iter__(self) -> Iterator[dict[str, Value]]:
        if self._killed:
            return iter(())
        # Subscribed here rather than on the first next(), so notifications
        # from changes made after iter() but before reading are kept.
        return self._follow(self._connection.subscribe_live(self))

    def _follow(
        self, notifications: Iterator[dict[str, Value]]
    ) -> Iterator[dict[str, Value]]:
        yield from notifications
        self._ended()

    def kill(self) -> None:
        """Stop the live query. Iterators over it end.

        Does nothing if the query has already ended. If the request fails the
        subscription stays alive, so the kill can be tried again.
        """
        if self._killed:
            return
        self._connection.kill(self, session_id=self._session_id)
        self._ended()

    def __enter__(self) -> "LiveSubscription":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.kill()


class SubscriptionTracker:
    """The subscriptions a connection handed out, held weakly, so that it can
    tell them when their query ends some other way: ``db.kill(id)``, a
    ``KILLED`` notification, a reset or detached session, or a closed
    connection."""

    def __init__(self) -> None:
        self._subscriptions: weakref.WeakValueDictionary[int, _Subscription] = (
            weakref.WeakValueDictionary()
        )

    def add(self, subscription: _Subscription) -> None:
        self._subscriptions[id(subscription)] = subscription

    def ended(self, live_id: str | None = None, keep: Container[str] = ()) -> None:
        """Mark the subscriptions to *live_id*, or to every query but those in
        *keep*, ended."""
        for key, subscription in list(self._subscriptions.items()):
            name = str(subscription)
            if (live_id is None and name not in keep) or name == live_id:
                self._subscriptions.pop(key, None)
                subscription._ended()  # pyright: ignore[reportPrivateUsage]
