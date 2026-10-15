"""Reconnecting a websocket that dropped, and what is replayed afterwards.

A websocket connection reconnects on its own when the socket drops
unexpectedly, unless it was built with ``reconnect=False``. Each attempt waits
longer than the last (``retry_delay`` seconds, multiplied by
``retry_delay_multiplier`` per attempt, capped at ``retry_delay_max`` and
offset randomly by up to ``retry_delay_jitter`` of itself), as in the JS SDK.

Once a new socket is open, the connection replays what the server forgot with
the old one: for the root session and every session from ``new_session()``,
the selected namespace and database, the variables from ``let``, and the
authentication; then every live query started with ``live()``, under a new
server-side id that the original id keeps routing to. A request that was in
flight when the socket dropped fails with ``ConnectionUnavailableError``
rather than being sent again, since it may already have run; a request made
while reconnecting waits for the replay to finish first.
"""

import random
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from surrealdb.connections.events import EventsMixin
from surrealdb.data.types.null import NullType
from surrealdb.types import Tokens, Value


@dataclass(frozen=True)
class ReconnectOptions:
    """How a websocket connection reconnects after the socket drops.

    Attributes:
        enabled: Reconnect at all.
        attempts: How many attempts to make before giving up, or ``-1`` for
            no limit.
        retry_delay: Seconds to wait before the first attempt.
        retry_delay_max: The longest wait between attempts, in seconds.
        retry_delay_multiplier: What each wait is multiplied by for the next.
        retry_delay_jitter: The fraction of each wait to offset it by, at
            random, so that many clients do not all return at once.
    """

    enabled: bool = True
    attempts: int = 5
    retry_delay: float = 1.0
    retry_delay_max: float = 60.0
    retry_delay_multiplier: float = 2.0
    retry_delay_jitter: float = 0.1

    def __post_init__(self) -> None:
        if isinstance(self.attempts, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.attempts, int
        ):
            raise TypeError("attempts must be an int, or -1 for no limit")
        if self.attempts < -1:
            raise ValueError("attempts must be at least 0, or -1 for no limit")
        for name in ("retry_delay", "retry_delay_max", "retry_delay_multiplier"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")
            if value < 0:
                raise ValueError(f"{name} must not be negative; got {value!r}")
        if not 0 <= self.retry_delay_jitter <= 1:
            raise ValueError(
                "retry_delay_jitter must be a fraction between 0 and 1; got "
                f"{self.retry_delay_jitter!r}"
            )

    @classmethod
    def coerce(cls, value: "bool | ReconnectOptions | None") -> "ReconnectOptions":
        """Accept ``True``, ``False`` or options, as the connections do."""
        if value is None or value is True:
            return cls()
        if value is False:
            return cls(enabled=False)
        if isinstance(value, ReconnectOptions):  # pyright: ignore[reportUnnecessaryIsInstance]
            return value
        raise TypeError(
            "reconnect must be True, False or ReconnectOptions, not "
            f"{type(value).__name__}"
        )

    def allows(self, attempt: int) -> bool:
        """Whether attempt number *attempt* (counting from 1) may be made."""
        return self.enabled and (self.attempts == -1 or attempt <= self.attempts)

    def delay(self, attempt: int) -> float:
        """Seconds to wait before attempt number *attempt* (counting from 1)."""
        base = self.retry_delay * self.retry_delay_multiplier ** (attempt - 1)
        jitter = random.uniform(-self.retry_delay_jitter, self.retry_delay_jitter)
        return max(0.0, min(base * (1 + jitter), self.retry_delay_max))


@dataclass
class SessionState:
    """What the server holds for one session, kept so it can be replayed."""

    namespace: str | None = None
    database: str | None = None
    variables: dict[str, Value] = field(default_factory=dict)
    access: str | None = None
    refresh: str | None = None

    def tokens(self) -> Tokens | None:
        if self.access is None and self.refresh is None:
            return None
        return Tokens(access=self.access, refresh=self.refresh)

    def fork(self) -> "SessionState":
        return replace(self, variables=dict(self.variables))


@dataclass
class LiveQuery:
    """A live query that can be started again on a new socket.

    ``logical`` is the id the caller was given and keeps using; ``current`` is
    the id the server knows it by on the socket in use, which changes each
    time the query is started again.
    """

    logical: UUID
    current: UUID
    table: Any
    diff: bool
    session_id: UUID | None


class SessionRegistry:
    """The state of the root session and of every attached session."""

    def __init__(self) -> None:
        self.root = SessionState()
        self.sessions: dict[UUID, SessionState] = {}
        self.live: dict[str, LiveQuery] = {}
        self.aliases: dict[str, str] = {}

    def state(self, session_id: UUID | None) -> SessionState:
        if session_id is None:
            return self.root
        state = self.sessions.get(session_id)
        if state is None:
            state = self.sessions[session_id] = SessionState()
        return state

    def find(self, session_id: UUID | None) -> SessionState | None:
        """The state held for *session_id*, without registering a new one."""
        if session_id is None:
            return self.root
        return self.sessions.get(session_id)

    def forget_session(self, session_id: UUID) -> None:
        self.sessions.pop(session_id, None)
        for key, live in list(self.live.items()):
            if live.session_id == session_id:
                self.drop_live(key)

    def clear(self) -> None:
        self.root = SessionState()
        self.sessions.clear()
        self.live.clear()
        self.aliases.clear()

    def add_live(self, live: LiveQuery) -> None:
        self.live[str(live.logical)] = live
        self.aliases[str(live.current)] = str(live.logical)

    def move_live(self, live: LiveQuery, current: UUID) -> None:
        self.aliases.pop(str(live.current), None)
        live.current = current
        self.aliases[str(current)] = str(live.logical)

    def drop_live(self, logical: str) -> LiveQuery | None:
        live = self.live.pop(logical, None)
        if live is not None:
            self.aliases.pop(str(live.current), None)
        return live

    def resolve(self, logical: str) -> str:
        """The id the server currently knows *logical* by."""
        live = self.live.get(logical)
        return str(live.current) if live is not None else logical

    def logical_of(self, current: str) -> str:
        """The id the caller holds for the server's *current*."""
        return self.aliases.get(current, current)


class SessionTrackingMixin(EventsMixin):
    """Keeps :class:`SessionRegistry` in step with what the server was told.

    The websocket transports call the ``_note_*`` methods after each request
    the server accepted, so that what is replayed after a reconnect is exactly
    what the server held before it.
    """

    _registry: SessionRegistry  # pyright: ignore[reportUninitializedInstanceVariable]

    @property
    def token(self) -> str | None:
        """The access token the connection's own session is authenticated with."""
        return self._registry.root.access

    @token.setter
    def token(self, value: str | None) -> None:
        self._registry.root.access = value

    @property
    def namespace(self) -> str | None:
        """The namespace selected on the connection's own session."""
        return self._registry.root.namespace

    @property
    def database(self) -> str | None:
        """The database selected on the connection's own session."""
        return self._registry.root.database

    def _note_use(
        self,
        session_id: UUID | None,
        namespace: str | NullType | None,
        database: str | NullType | None,
    ) -> None:
        """Record a ``use``: a string selects, ``Null`` clears, ``None`` keeps."""
        state = self._registry.state(session_id)
        if namespace is not None:
            state.namespace = None if isinstance(namespace, NullType) else namespace
        if database is not None:
            state.database = None if isinstance(database, NullType) else database
        self._emit("using", state.namespace, state.database, session_id)

    def _note_reset(self, session_id: UUID | None) -> None:
        """The server cleared the session: selection, variables and auth."""
        state = self._registry.state(session_id)
        had_auth = state.access is not None or state.refresh is not None
        had_selection = state.namespace is not None or state.database is not None
        state.namespace = state.database = state.access = state.refresh = None
        state.variables.clear()
        if had_selection:
            self._emit("using", None, None, session_id)
        if had_auth:
            self._emit("auth", None, session_id)

    def _note_revoked(self, session_id: UUID | None, refresh: str) -> None:
        """A revoked refresh token cannot be used again, so stop holding it."""
        state = self._registry.find(session_id)
        if state is not None and state.refresh == refresh:
            state.refresh = None

    def _token_pair(
        self, tokens: Tokens | None, session_id: UUID | None, purpose: str
    ) -> dict[str, str]:
        """The ``{access, refresh}`` object the server takes for *purpose*."""
        held = tokens
        if held is None:
            state = self._registry.find(session_id)
            if state is None:
                raise ValueError(
                    f"{purpose} names session {session_id}, which this "
                    "connection does not hold: pass its Tokens explicitly, or "
                    "use a session from new_session() that is still open"
                )
            held = state.tokens()
        if held is None or held.refresh is None:
            raise ValueError(
                f"{purpose} needs a refresh token: pass the Tokens that signin() "
                "or signup() returned for an access method defined WITH "
                "REFRESH, or sign in with one on this session first"
            )
        pair = {"refresh": held.refresh}
        if held.access is not None:
            pair["access"] = held.access
        return pair

    def _note_let(self, session_id: UUID | None, key: str, value: Value) -> None:
        self._registry.state(session_id).variables[key] = value

    def _note_unset(self, session_id: UUID | None, key: str) -> None:
        self._registry.state(session_id).variables.pop(key, None)

    def _note_tokens(self, session_id: UUID | None, tokens: Tokens) -> None:
        state = self._registry.state(session_id)
        state.access = tokens.access
        state.refresh = tokens.refresh
        self._emit("auth", tokens, session_id)

    def _note_authenticated(self, session_id: UUID | None, token: str) -> None:
        """Record an access token given on its own.

        A refresh token belongs to the access token it came with, so one held
        for a different access token is dropped rather than paired with this.
        """
        state = self._registry.state(session_id)
        if state.access != token:
            state.refresh = None
        state.access = token
        self._emit("auth", Tokens(access=token, refresh=state.refresh), session_id)

    def _note_signed_out(self, session_id: UUID | None) -> None:
        state = self._registry.state(session_id)
        state.access = None
        state.refresh = None
        self._emit("auth", None, session_id)
