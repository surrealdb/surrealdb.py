# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- File support. SurrealDB stores files in buckets - in memory, on disk, or on
  object storage such as S3 - and `File` is a reference to one: a bucket plus a
  key. It carries no bytes and is not a Python file object.

  `db.files` provides typed helpers over the `file::*` functions on all six
  connection classes, and on sessions and transactions too, so
  `txn.files.put(...)` runs inside that transaction:

  ```python
  from surrealdb import File

  avatar = File("images", "/photos/avatar.png")
  db.files.put(avatar, png_bytes)
  png_bytes = db.files.get(avatar)          # None if absent
  meta = db.files.head(avatar)              # FileMetadata | None
  for entry in db.files.list("images", prefix="/photos", limit=50):
      print(entry.file.key, entry.size)
  ```

  `put`, `put_if_not_exists`, `get`, `exists`, `delete`, `head`, `list`, `copy`,
  `copy_if_not_exists`, `rename` and `rename_if_not_exists`. `get` and `head`
  return `None` for a file that does not exist rather than raising; `delete` is
  idempotent; `list` raises when the *bucket* is missing, because an empty bucket
  and a misspelled one are different mistakes.

  The wire format is CBOR tag 55 carrying `[bucket, key]`, matching the
  JavaScript SDK's `TAG_FILE_POINTER`. A key is normalised to start with `/`, as
  it is there, so `File("b", "a.txt")` and `File("b", "/a.txt")` are one file.

  Every helper binds the `File` as a parameter rather than writing it into the
  query, which is not a style choice: SurrealQL's `f"bucket:/key"` literal
  accepts only `[A-Za-z0-9_-./]` and has **no escape mechanism**, so a key with a
  space, an accent or an emoji cannot be expressed as a literal at all. Bound,
  every key works. `str(File(...))` renders the literal form for logging and is
  display-only; `File.is_literal_safe()` reports whether a given file could be
  written into a query.

  `list()` takes `limit`, `prefix` and `start` as keyword arguments rather than
  an options dict because the server *silently ignores* option keys it does not
  recognise - a passthrough dict would turn `limti=2` into "every file in the
  bucket" with nothing to indicate why. `start` is exclusive.

  Buckets are an experimental server feature: the server must be started with
  `SURREAL_CAPS_ALLOW_EXPERIMENTAL=files`, and the tests detect that capability
  rather than a version number, since the same build has it or not depending on
  how it was started. The embedded engine does not enable it, so `db.files` on a
  `mem://` connection reports the server's own "experimental files feature"
  error.


## [3.0.0-beta.8] - 2026-08-21

The release that makes the memory split usable. `surrealdb-memory 1.0.0-beta.1`
is already on PyPI, but every install path the docs describe - the `[memory]`
extra and the `surrealdb.memory` import - lives in this package, so until now
they pointed at nothing.

### Changed

- **Breaking:** the memory client has moved out of this package. It was
  `surrealdb.spectron`, bundled into every install; it is now the separate
  `surrealdb-memory` distribution, installed with `pip install 'surrealdb[memory]'`
  and imported as `from surrealdb.memory import Memory`.

  The point is release cadence, not size. Bundled, its version *was* the SDK's,
  so a change to the memory service's API forced a full SDK release - the whole
  wheel matrix plus the Rust embedded build across six platforms - and every SDK
  patch republished the memory client unchanged. The `[memory]` extra depends on
  `>=`, deliberately unlike `[embedded]`'s exact pin, so you can hold `surrealdb`
  at 3.x and move `surrealdb-memory` across its own majors. (`embedded` pins
  exactly because that extension is compiled against the SDK and has to match;
  a client that speaks HTTP to a separate service does not.)

  Product names are gone from the API along with it. `Spectron` and
  `AsyncSpectron` are now `Memory` and `AsyncMemory`; `SpectronError` and its
  four subclasses are `MemoryServiceError`, `MemoryAPIError`, `MemoryAuthError`,
  `MemoryNotFoundError` and `MemoryScopeError`. The base is
  `MemoryServiceError` rather than `MemoryError` on purpose - `MemoryError` is a
  Python builtin, and shadowing it means a caller's `except MemoryError:` stops
  catching an interpreter out-of-memory while a real service failure goes
  uncaught by code expecting the builtin. The two classes are unrelated, so both
  directions fail silently.

  `surrealdb.memory` remains the supported import path: it is a small forwarding
  module in the SDK, so nothing about the short spelling changes. It is a
  *module* and not a package because two distributions writing into one
  `surrealdb/memory/` directory installs without complaint and then breaks on
  uninstall - the survivor imports as an empty namespace package, so
  `import surrealdb.memory` still succeeds while exporting nothing.

  Migrating is two substitutions:

  ```python
  # before
  from surrealdb.spectron import Spectron, AsyncSpectron, SpectronError
  # after — pip install 'surrealdb[memory]'
  from surrealdb.memory import Memory, AsyncMemory, MemoryServiceError
  ```

  Without the extra installed, `surrealdb.memory` still imports and any
  attribute names what is missing and how to get it, rather than failing with a
  bare `ModuleNotFoundError`.

  The first release of it is `surrealdb-memory` **1.0.0-beta.1**, and the extra
  depends on `>=1.0.0b1` rather than `>=1.0`. That is load-bearing: a specifier
  that does not itself name a pre-release excludes them, so a `>=1.0` floor would
  leave `surrealdb[memory]` resolving to nothing at all while the client is on
  its beta line. Two tests read both pyproject files and fail if the floor stops
  admitting the version the addon declares, or stops being a `>=` floor.

  Releases are now selected by tag, because a memory release must not require an
  SDK bump. `v<version>` releases `surrealdb` and `surrealdb-embedded`;
  `memory-v<version>` releases `surrealdb-memory`. Previously every release ran
  the whole Rust wheel matrix regardless - harmless in that `skip-existing`
  turns a re-publish of an unchanged version into a no-op, but nine wheel builds
  ran to produce artifacts that were discarded, and a transient failure in any of
  them turned a release that only shipped the memory client red.

## [3.0.0-beta.7] - 2026-08-15

The surfaces a new user meets before they call a method: the PyPI page, the
migration table, the export list, and the examples. A pre-stable audit across
API parity, packaging, error contracts and documentation found nothing that a
later release could not fix, so this is the cheap half - the things that are
simply wrong today.

### Added

- The seven usable geometry classes are now exported from `surrealdb`:
  `GeometryPoint`, `GeometryLine`, `GeometryPolygon`, `GeometryMultiPoint`,
  `GeometryMultiLine`, `GeometryMultiPolygon` and `GeometryCollection`. The
  package used to export exactly one geometry name - `Geometry`, the base class -
  and that is the single one you cannot send: it constructs, then fails at encode
  time with `cannot encode Geometry`. `Geometry` is still exported, for
  `isinstance` checks and annotations.
- Python 3.14 is supported, tested and declared. The pure-Python package needed
  no change, and the embedded extension is built `abi3-py39`, so the existing
  wheel already runs on it. Both are now in the CI matrix rather than only in the
  classifier list.

### Fixed

- The README's migration table illustrated the `query()` return-shape change
  with `SELECT 1`, which is a parse error on every SurrealDB version. It is now
  `RETURN 1`, which runs.
- Four README links were relative. The README is the PyPI long description, and
  PyPI renders it with no repository around it, so those four 404'd on the
  project page.
- Every example declared `surrealdb>=1.0.7`, which resolves to 2.0.0 and cannot
  import the 3.x code sitting in the same directory. All 21 declarations across
  the 12 example projects now ask for `>=3.0.0`.
- The fastapi example could not be imported by following its own README: it
  annotates `EmailStr` without depending on `pydantic[email]`.
- The logfire example crashed twice. `logfire.configure(console=True)` raises
  `'bool' object has no attribute 'span_style'` before any tracing starts, and
  the example read `query()` in the 2.x shape - one `TypeError`, and a user count
  that reported `1` for any query because it measured statements rather than rows.
- Four `xfail` markers described an SDK that no longer exists. Three were waiting
  on a `Table` round trip that SurrealDB has since fixed, and one asserted that
  `live()` over HTTP returns a `UUID` when it has raised `UnsupportedFeatureError`
  since the transports were made consistent. An `xfail` records only *that*
  something failed, so the last one would have stayed green if `live()` had begun
  raising `AttributeError` from a typo.

## [3.0.0-beta.6] - 2026-08-15

One user-visible addition, and a linter that had been switched off without
anyone noticing.

### Added

- `select(fields=[...])` narrows the projection, so the server sends only the
  fields asked for rather than the whole record - on all six connection classes.
  The capability was always reachable through `query("SELECT a, b FROM $r")`;
  this is the spelling on the method that already binds the resource for you and
  composes with `into=`. A dot walks into a nested object, and each segment is
  escaped separately: escaping a whole `"address.city"` would ask for a field of
  that literal name, which the server answers with a null rather than an error.
  A field list cannot be parameter-bound - SurrealQL has no `SELECT $f` - so it
  is the one part that must be inlined, and every name is escaped on the way in.
  `id` is not included unless you ask for it, exactly as in SurrealQL, so a model
  passed to `into=` that declares one needs `fields=["id", ...]`. `fields=None`
  is the default and emits the same statement as before.

### Fixed

- The linter had been checking almost nothing. `select` in the ruff config
  *replaces* ruff's defaults rather than adding to them, so setting it to
  `["I", "UP"]` turned pyflakes off across the whole project - nothing had been
  checking for unused imports, unused variables or undefined names. Turning the
  defaults back on and adding bugbear, comprehensions, pie, simplify and the
  ruff-specific rules found 42 unused imports and 12 unused variables. Two other
  blind spots went with it: `src/surrealdb/__init__.py` was excluded from ruff
  entirely, and CI pointed it at `./src` alone, so the test suite was linted and
  formatted by nothing. No behaviour changes, but eight `pytest.raises(Exception)`
  are now narrowed to what the code actually raises, so they no longer pass on an
  unrelated `AttributeError`.


## [3.0.0-beta.5] - 2026-08-15

The second review pass over the 3.0.0 surface, and the first that verified its
own fixes: twenty-two defects found by an adversarial review of the shipped
artifacts, twelve regressions those fixes introduced, and six tests that passed
against the very code they were written to guard.

### Added

- `Null` and `NullType`. SurrealDB's NULL and NONE are different values, and both used to decode to Python's `None` - which encodes back as NONE, so an ordinary read-modify-write silently *deleted* every NULL field it touched. `None` still means NONE; `surrealdb.Null` is the NULL sentinel. It is falsy, is not equal to `None`, and survives pickling and copying. If you have code comparing a database value with `is None`, check whether the column can be NULL.
- `SurrealSet`, the type a `set<T>` column now decodes to. A Python `set` cannot hold the members SurrealDB allows - `set<object>` raised `unhashable type: 'dict'` and lost the whole response - and a plain `list` loses the type, so writing a record back either failed on a schemafull field or silently turned it into an array and dropped the deduplication. `SurrealSet` is a `list` subclass that re-encodes under the set tag, so both hold. Writing a plain Python `set` is unchanged.
- `RecordIdValue`, the union of what SurrealDB accepts as a record id, for annotating or casting against.
- `Bound`, `BoundIncluded` and `BoundExcluded`. `Range` was exported without them, so the one exported name could not actually be constructed from the public package.

### Changed

- **Breaking.** `RecordID` and `Table` now reject arguments they cannot use. A table name must be a `str`; a record id must be one of `str`, `int`, `uuid.UUID`, `list`, `tuple`, `dict` or `Range`. Both used to accept anything: `Table(None)` was refused by nothing and *succeeded*, writing the row to a table literally named `None` where no query against the intended table would ever find it, on both 2.x and 3.x. `RecordID("t", 1.5)` and friends encoded cleanly and came back as `ValidationError: Parse error`, naming neither the argument nor the mistake. Values decoded from the wire deliberately bypass the check, so a future server's new id type can never make a record unreadable. Also breaking: `RecordID(Table("x"), 1)` worked on 2.0.5 and now raises everywhere (it was already a parse error on 3.x), and a `bytes` record id renders as `t:b'xy'` rather than being decoded - decoding raised `UnicodeDecodeError` on non-UTF-8 and rendered `b"xy"` identically to the *string* id `"xy"`, which is a different record.
- **Breaking.** The embedded engine now enforces authentication. It was built with authentication disabled, which makes the engine skip every permission check for an anonymous session - and `invalidate()`, whose whole job is to drop the caller's identity, reset the session to exactly that. Invalidating therefore *raised* privilege: a record user who could not read a `PERMISSIONS NONE` table, and could not run `INFO FOR ROOT`, could do both afterwards. The datastore is now built with authentication on and the implicit session seeded as root owner, so opening an embedded database and using it without signing in is unchanged while `invalidate()` leaves the session anonymous and denied, matching websocket and HTTP.
- A `RecordID` whose id is a `Range` now returns every record in the range. It was classified as a single-record target and unwrapped to the first row, so three records were read, one was returned, and nothing said the other two had been dropped; `delete()` and `update()` reported writing one record while writing all of them. The equivalent `"person:1..=3"` string was always treated as multi-record, so the two spellings of one target disagreed.

### Fixed

- Identifiers SurrealDB will not accept bare are now quoted. The rule was `str.isalnum()`, which Python answers True for a letter or digit of *any* script, so `héllo`, `таблица`, `表格` and the superscript `²` were judged safe and inlined unquoted - and `INSERT` is the one statement whose target the SDK inlines rather than binds, so inserting into a non-ASCII table name failed with `Parse error: Invalid token`. A leading digit (`1tbl`) was passed through for the same reason and refused for a different one. `str(record_id)` also escapes the table half now, not just the id; it rendered as unparseable SurrealQL for exactly those names, from the method the docs point at for composing query text.
- Three dependency floors that could not work. `websockets>=14.1`, `pydantic-core>=2.10.0` and `aiohttp>=3.14.0` are the versions the SDK actually needs; the declared minimums were lower than the APIs in use, so a resolver honouring old pins produced an install where `import surrealdb` raised. CI now runs the suite against the declared floors so this cannot drift again.
- A read-modify-write no longer corrupts data in six ways. A nanosecond timestamp lost its last three digits and stored the truncated value back; a naive `PreciseDatetime` was encoded as local time rather than UTC; a `Range` with an unbounded end could never be written back; `Duration.parse` accepted strings the server rejects and turned them into *different* durations rather than errors (`"1.5s"` parsed as the `5s` inside it, `"-1s"` lost its sign); a `set<T>` field lost its type; and a NULL field was deleted. Each is now a round trip that holds.
- `run()` sees `let()` bindings on HTTP, and `update()` on a record that does not exist answers `None` rather than an empty list. The HTTP transports replay session variables themselves, and were not replaying them into `run()`; `update()` returned `[]` for an absent record, which is neither the `dict` the overloads promise nor the `None` `select()` gives, so `if db.update(rec, data):` was False for a missing record but `db.update(rec, data)["field"]` raised `TypeError`.
- One malformed request no longer fails its neighbours. A protocol error arrives with no `id`, and the async websocket failed *every* pending future when it saw one - so three unrelated queries on the same connection all came back `Parse error` because a fourth, concurrent one was malformed. The error is now held and delivered to the request it belongs to. A websocket whose reader had stopped is also reopened rather than left permanently wedged.
- Every live-query notification is delivered, and a killed subscription ends. The blocking transport dropped notifications that arrived between an RPC's send and its reply, and `kill()` left same-connection subscribers waiting forever on 2.x, which sends no `KILLED` frame. Async subscribers are now woken when the connection dies instead of waiting on a queue nothing will ever fill.
- The connection-type aliases resolve at runtime. `BlockingSurrealConnection` and `AsyncSurrealConnection` are exported for annotating a connection, and were built from forward-reference *strings* - so `typing.get_type_hints`, `inspect.signature(eval_str=True)`, pydantic and FastAPI all raised `NameError` naming a class the user had never imported. They are built from the real classes now, and a sweep guards every public alias against the same defect.
- `with db:` on a connection that is already open keeps it. Entering assigned a fresh socket unconditionally, and a websocket *is* the server-side session, so the sign-in went with it and the first statement inside the block came back `NotAllowedError`. Both HTTP transports leaked a connection pool per re-entry the same way.
- `connect()` after `close()` reopens the embedded engine. `close()` shuts the datastore down for good while the native `connect()` was a no-op returning success, so reconnecting reported a working connection and then refused every request. A reopened `memory://` database starts empty; a file-backed one keeps its data.
- An async websocket used from a second event loop says so. It failed with a bare `ValueError` from inside asyncio and then stayed wedged; it now raises `ConnectionUnavailableError` naming the cause and the fix, and `close()` works across loops so the advice is actionable.
- An async websocket dropped without `close()` releases its socket. The reader task held a strong reference to the connection, so it was never collected and no finaliser could run - forty dropped connections held forty file descriptors, and `asyncio.run` closing its loop printed `Task was destroyed but it is pending!` on the way out. It now holds a weak reference and releases the socket on collection, with a `ResourceWarning` like an unclosed file.
- A record that does not match an `into=` model says which model and which fields, inside the `SurrealError` tree, instead of a bare `TypeError` raised from inside the model.
- A bare `Range` as a resource target is refused with an explanation instead of `TypeError: argument of type 'Range' is not iterable` - and the error next to it no longer recommends passing one.
- Six README examples that did not work: the `into=` block wrote a field its own model did not declare, the sync block deleted a table nothing had created, and six live-query examples iterated `subscribe_live` without awaiting it. The runnable blocks are now executed by the test suite rather than only read.

- Sending a Python `set` to a SurrealDB 2.x server now says what went wrong. Sets are encoded with SurrealDB 3.x's CBOR set tag; 2.x has no set representation at all - it returns SurrealQL sets as plain arrays - so it answered with a bare `Encountered an unknown CBOR tag`, which named neither the cause nor the remedy. That message now carries both. The hint is attached from the server's own wording, so nothing else is affected and no version probe is added; the trade-off is that SurrealDB 2.0.x reports the same rejection as `Invalid Request`, which is too generic to attach anything to safely. The README's new *Talking to a SurrealDB 2.x server* section covers the limitation for both.
- The README now documents that error *kinds* need SurrealDB 3.x. The subclasses below `ServerError` come from the `kind` the server reports, and 2.x does not send one - its error payload carries only a generic `-32000` code and a message - so every server-side failure arrives as `InternalError` there. `except SurrealError` and `except ServerError` work everywhere, but a narrower `except ThrownError` silently never matches on 2.x. The SDK cannot recover the classification, because it is not on the wire; saying so is the only honest fix.

- A rejected `authenticate()` no longer destroys the connection. Both HTTP transports assigned the token to the connection *before* sending it, so a token the server refused stayed attached to every later request - including the `signin()` that would have recovered the connection, which the server then answered with `401`. One failed `authenticate()` left the connection permanently unusable, with no way back short of building a new one and nothing anywhere saying so. The token now authorises the `authenticate` request alone, and is adopted as the connection's identity only once the server accepts it. A token the SDK's own request schema rejects - one that is not JWT-shaped, and so never leaves the process - did exactly the same damage, and is covered too. The websocket transports already assigned after the reply arrived; they gained tests so all four stay in step.

- A closed blocking websocket connection can be opened again. `close()` closed the socket but kept the reference to it, so `connect()` saw a connection and returned without doing anything, and every call after it failed against the dead socket - `connect()` after `close()` was a silent no-op, on the one transport whose async twin had always cleared it. `close()` now drops the reference, `__exit__` goes through it, and both `connect()` and the lazy reconnect inside `_send` open a fresh socket. That socket is a new server-side session, so it starts unauthenticated and with no namespace or database selected; sign in and `use()` again after reconnecting, as `close()` now documents.
- `connect(url)` re-points a connection that is already open. Both websocket transports returned early whenever a socket existed, so the new URL was silently discarded and the connection carried on talking to the old endpoint while reporting the new one - the docstring described a re-point that never happened. Passing the url the connection is already using is still a no-op: reconnecting costs the server-side session, so a defensive `connect(url)` must not quietly undo a completed `signin()`.
- A blocking websocket connection dropped without `close()` no longer leaks its socket and threads. Every open websocket holds a TCP socket and two `websockets` worker threads (`recv_events` and `keepalive`), and nothing released them, so a program that built connections in a loop and let them fall out of scope accumulated all three per connection until the process exited - five discarded connections left ten threads running. The socket is now released when the connection is collected. That is deliberately not the closing handshake `close()` performs: the graceful path joins the reader thread, which never returns at interpreter shutdown - by then the reader has been stopped without releasing its lock - and which stalls whoever dropped the last reference for the full close timeout whenever the peer has gone quiet.

- Live queries are refused with a `SurrealError` on the transports that cannot serve them. The README documents them as WebSocket-only, but the four non-websocket connection classes disagreed with it and with each other. Embedded `subscribe_live()` raised a bare `AttributeError` naming an internal attribute, because both embedded constructors hand-copied a subset of the attributes their parents set and that one was not in it; embedded `live()` and `kill()` reached the engine and came back as `Unable to perform the realtime query`, which does not say why; and on HTTP all three raised `NotImplementedError`, which is not a `SurrealError`, so the single `except SurrealError` the README promises covers every failure missed them - while `attach()` on the very same object was covered. All three now raise `UnsupportedFeatureError` giving the reason, on both HTTP and both embedded connections, and `subscribe_live()` raises on the call rather than on the first `next()`, so the error points at the line that made the mistake. The embedded constructors now run their parent's - it opens nothing, it only sets attributes - so a future divergence cannot strand an inherited method again.

- Nanosecond precision survives a round trip. `datetime` resolves to microseconds, so decoding a SurrealDB timestamp dropped its last three digits - and writing that value back stored the truncated form, so an ordinary read-modify-write destroyed precision *in the database*, silently and with no error. Timestamps now decode to `PreciseDatetime`, a `datetime` subclass that keeps the remainder in `.nanosecond` and re-encodes it in full. It is a `datetime` in every other respect: `isinstance` holds, it compares and sorts against plain `datetime` values, and pickle and copy round-trip, so existing code is unaffected. Encoding a plain `datetime` is untouched - the hook is registered for the subclass alone. One limit is inherent: `datetime` arithmetic builds results through constructors that know nothing of the extra field, so a computed value carries `nanosecond == 0`. Precision survives storage and retrieval, but not computation.

- A zero-valued `Duration` no longer destroys the response it appears in. The server omits trailing zero components, so a zero duration arrives as an *empty* CBOR array; the decoder handled one and two elements and indexed `[0]` otherwise, raising `IndexError` and losing the entire result rather than one field. A `Duration(0)` written by the SDK itself could never be read back.
- An integer SurrealDB cannot represent is now refused instead of being silently corrupted. SurrealDB stores integers as signed 64-bit, but a Python int above the signed maximum still fits CBOR's unsigned range, so it encoded cleanly and the server reinterpreted the bits: `2**63` came back as `-9223372036854775808` and `2**64 - 1` as `-1`, with no error raised anywhere. Values outside the signed 64-bit range now raise `ValueError` at encode time, naming the range and suggesting a string or `Decimal`. This is deliberately a builtin rather than a `SurrealError`, like the encoder's other caller-mistake case.

- A timed-out websocket RPC no longer desynchronises the connection. The deadline added to stop protocol errors hanging forever introduced its own failure: the request had already been sent, so the server's late reply stayed in the socket and the next call read *that* instead of its own, mismatching ids from then on and never recovering. Abandoned request ids are now remembered and their late replies dropped, so a timeout costs one call rather than the connection. This was never released - it existed only on `main`.
- An async websocket connection is no longer bricked by a single bad frame. `_recv_task` ended on the first frame it could not handle - a protocol-level error carrying no `id`, or anything that failed to decode - and because the socket stayed open, `connect()` saw a live socket and did nothing while every later request waited on a future nothing would ever resolve. With no timeout on that path the caller hung indefinitely, and the reported error claimed the connection had closed when it had not. The receive loop now survives a bad frame and hands the failure to the callers waiting on it, every RPC wait is bounded by the same 30 second deadline the blocking transport uses, and `connect()` re-establishes a connection whose reader has stopped. The blocking transport was given this treatment when the same defect was found there; the async twin was missed.

- `create`, `update`, `upsert` and `insert` treat an explicit `data=None` the same way on every transport. The async connections used `None` as the default for `data`, so an explicit `None` was indistinguishable from omitting the argument: they returned an unconfigured builder and silently ignored it, while the blocking connections ran `CONTENT NULL` and raised. The same call therefore did nothing on async and failed on blocking. The async side now uses the same sentinel the blocking side already did, so both raise. `None` remains a legal *value* meaning `CONTENT NULL`; it is only disqualified as the marker for "not supplied".
- `AsyncSurrealSession` and `BlockingSurrealSession` expose `subscribe_live()`. Both already had `live()` and `kill()`, so a session could start a live query it had no way to consume - callers had to reach past the wrapper to the underlying connection.

### Removed
- `set_token()` on the HTTP connections. It existed on those two classes only, was undocumented and unreferenced, and assigned the token without the `AUTHENTICATE` call that validates it - so a caller could believe they were authenticated while the server had never seen the token, with the failure surfacing later on an unrelated call. `token` is a public attribute, so `db.token = ...` does everything the method did; `authenticate()` remains the way to authenticate for real.

- `surrealkv+versioned://` works. The scheme is documented in the README, advertised in the 3.0.0-alpha changelog as a feature, and named in `UnsupportedEngineError`'s own message as a valid embedded form - but every path failed with `Unable to load the specified datastore`, because the engine matches storage flavours exactly and takes MVCC versioning as a *query parameter* rather than as part of the scheme. The extension now translates `surrealkv+versioned://<path>` into the form the engine parses, appending to any query string the caller supplied rather than replacing it. Time-travel queries (`SELECT ... VERSION d"..."`) return the value as of that moment, and are still correctly rejected on a plain `surrealkv://` store.
- Operational failures that used to escape the `SurrealError` hierarchy now stay inside it, so `except SurrealError` covers them. A malformed URL raised a bare `ValueError` from `urlparse` or from `.port` - an out-of-range port, a non-numeric port, an unterminated IPv6 literal - even though an unrecognised *scheme* was already mapped, so the same call landed inside or outside the hierarchy depending on which part of the URL was wrong. These now raise the new `InvalidUrlError`. An embedded connection used after `close()` raised a bare `RuntimeError` from the native extension where the websocket and HTTP transports raise `ConnectionUnavailableError` for the same mistake; every failure from the engine is now mapped, with the extension's own message kept as `__cause__`. A CBOR tag the SDK cannot decode - a value from a newer server - now raises `UnexpectedResponseError` instead of `BufferError`.
- A value the SDK cannot encode now raises `TypeError` rather than `BufferError`, and names the offending type and the supported ones. This is deliberately *not* a `SurrealError`: passing an unserialisable object is a caller mistake, and Python's answer to that is `TypeError`. Wrapping it would hide programming errors inside the `except SurrealError` that exists for operational failures - the same reason the SDK's argument validation keeps raising `ValueError`.

- A `Duration` can be sent to the database again. The CBOR encoder tagged it 13 - the *string* form - while carrying the `[seconds, nanoseconds]` array payload that belongs under tag 14, so every write containing a `Duration` was rejected by the server with HTTP 400, on every transport and against the embedded engine. Reading a `Duration` always worked, and the SDK's own decoder accepts either shape, so an encode/decode round trip passed and hid the defect. The regression test asserts the emitted wire tag rather than the round trip.
- The blocking websocket connection no longer hangs forever on a protocol-level error. SurrealDB answers a request it cannot parse with an error frame carrying no top-level `id`, and `_send` classified any id-less frame as a live-query notification - so the only reply the call would ever get was discarded and the receive loop blocked on `recv()` indefinitely. Ordinary calls triggered it, such as passing an integer too large to encode. Id-less frames carrying an error are now raised, and every RPC read is bounded by a 30 second deadline matching the HTTP transports, so no reply can block a caller forever.
- The embedded examples in the README no longer call `signin()`. Embedded connections have no server and no root user, so every one of the three quick-start examples in that section failed with `NotAllowedError` when run as written - and that section renders on the PyPI project page. `examples/embedded/README.md` also still told readers the engine ships with `pip install surrealdb`; it now shows the `embedded` extra, like the main README.
- `connect()` now exists on `BlockingWsSurrealConnection`. It was the only connection class without it, so calling `connect()` raised `AttributeError` there while the other five transports connected - the same transport-agnostic breakage that adding `connect()` to the HTTP connections in 3.0.0-beta.4 was meant to remove. It opens the socket eagerly (the connection otherwise connects lazily on first use), is a no-op when already connected, and re-points the connection when passed a url, matching the other transports. Both connection templates now declare `connect()` as well, so a transport that omits it fails with a diagnosable `NotImplementedError` rather than `AttributeError`.
- The README no longer states that the embedded database is included in the default install. It is an optional native extension behind the `embedded` extra, so the documented `pip install surrealdb` left readers without the engine they had just been told they had. The section now shows `pip install 'surrealdb[embedded]'`, and its source-build command gained the `--manifest-path embedded/Cargo.toml` it needs to build the Rust crate rather than the root project.

## [3.0.0-beta.4] - 2026-08-10

Seven defects found by verifying the 3.0.0-beta.3 artifacts as a user installs them, rather than from the working tree. Most sit on the default `pip install surrealdb` path, which the test suite never exercised because it always has the optional engine present.

### Fixed
- `from surrealdb import *` no longer raises `AttributeError` on a plain `pip install surrealdb`. `__all__` advertised `AsyncEmbeddedSurrealConnection` and `BlockingEmbeddedSurrealConnection` unconditionally, but both are imported under a `try`/`except ImportError` and are absent without the optional `surrealdb[embedded]` engine - so the default install exported two names that did not exist, breaking star imports and anything that walks `__all__`. They now join `__all__` only when the engine is present, and accessing either without it raises an `AttributeError` naming the extra to install.
- An unsupported URL scheme now raises `UnsupportedEngineError` rather than a bare `ValueError` escaping from enum construction. `Surreal("ftp://...")`, `Surreal("rocksdb://...")` and `Surreal("localhost:8000")` all previously raised `ValueError: '...' is not a valid UrlScheme`, which `except SurrealError` did not catch - contradicting the guarantee that every failure the SDK raises is a `SurrealError`. The original `ValueError` is preserved as `__cause__`. **This changes the exception type**: code catching `ValueError` from connection construction should catch `SurrealError` (or `UnsupportedEngineError`) instead.
- `Surreal("memory")` works. The bare form is documented in the README as equivalent to `mem://` and is named as valid in `UnsupportedEngineError`'s own message, but `urlparse` reports an empty scheme without a `://` separator, so it raised `ValueError: '' is not a valid UrlScheme`. Only the documented bare spellings are matched, so scheme-less nonsense such as `Surreal("http")` is still rejected.
- The `surrealdb-embedded` wheel now ships a `py.typed` marker. It already included hand-written stubs for the native module (`_ext.pyi`), but PEP 561 requires type checkers to ignore stubs in a package that is not marked, so the stubs had no effect.
- `connect()` works on the HTTP connections. Both inherited the template default, which raised `NotImplementedError`, while the websocket transports connected - so transport-agnostic code calling `connect()` broke on HTTP alone. HTTP opens no persistent connection, so it is accepted as a no-op, and passing a url re-points the connection exactly as the websocket transports do.
- A trailing slash on the endpoint no longer doubles up in the `/rpc` URL. Every remote transport builds its endpoint as `f"{raw_url}/rpc"`, so `Surreal("http://host/")` produced `http://host//rpc` - visible to users in connection error messages. `Url.raw_url` now drops a trailing slash when there is a host to drop it from, leaving embedded forms such as `mem://` untouched.

### Changed
- The source distribution now contains only what is needed to build the package and run its tests against the source: `src`, `tests`, `README.md`, `LICENSE`, `CHANGELOG.md` and `pyproject.toml`. It previously shipped the entire working tree - CI workflows, editor config, Docker files, and the Rust crate belonging to the separate `surrealdb-embedded` package - which made it 480 KB against a 142 KB wheel. The wheel is unchanged.

## [3.0.0-beta.3] - 2026-08-10

A small correctness and dependency release. Embedded connections now report the engine version they actually run, and the `aiohttp` floor moves onto the release carrying CVE-2026-34993's fix.

### Fixed
- `version()` on an embedded connection now reports the SurrealDB engine version rather than the version of the `surrealdb-embedded` extension. The RPC handler formatted the extension crate's own `CARGO_PKG_VERSION`, so `mem://`, `file://` and `surrealkv://` connections answered `surrealdb-3.0.0-beta.2` while the engine they actually run is `surrealdb-core` 3.2.4 - the opposite of what the same call returns over HTTP or WebSocket, and misleading in the very release that moved the embedded engine to 3.2. Both the async and blocking implementations now read `surrealdb_core::env::VERSION`, which is compiled into the engine and so cannot disagree with what the wheel links. The extension's own version remains available as `importlib.metadata.version("surrealdb-embedded")`. Embedded version strings carry no `+<date>.<sha>` build metadata, because that suffix is derived from a git checkout of the SurrealDB monorepo and does not exist for an engine built from a published crate.

### Changed
- The minimum `aiohttp` is now 3.14.0, up from 3.13.4. 3.14.0 is the first release carrying the fix for CVE-2026-34993 (GHSA-jg22-mg44-37j8) in `CookieJar.load()`; the SDK never touches `CookieJar`, so the path was not reachable through it, but the floor now keeps users off the affected range. aiohttp 3.14 still supports Python 3.10, so this costs no platform coverage.
- The async HTTP tests no longer mock `aiohttp` with `aioresponses`; they run against a throwaway local `aiohttp` server instead. This removes the `aiohttp<3.14` resolution cap and the `aioresponses` test dependency entirely, so the suite now runs on the `aiohttp` users actually install rather than on a version pinned below it. The cap existed because `aioresponses` cannot construct aiohttp 3.14's `ClientResponse`, and upstream is not moving: its default branch has been unchanged since April 2026, four aiohttp-3.14 pull requests are open and unmerged, and aiohttp's own maintainers have declined to accommodate it. Because the cap was resolution-only, every user on every supported Python already received 3.14.x - a combination CI had never exercised. Test counts are unchanged, and the replacement asserts strictly more in places: real connection refusals and real timeouts now replace injected exceptions, and several cases gained `__cause__`, `.url` and `.kind` assertions that the mock could not express.

## [3.0.0-beta.2] - 2026-08-10

A maintenance beta. No API changes: the notable part is that the embedded engine moves from SurrealDB 3.0 to 3.2, and that the dependency surface is now watched rather than hand-bumped.

### Changed
- The `surrealdb-embedded` extension now builds against `surrealdb-core` 3.2.4, up from 3.0.5, so `mem://`, `file://` and `surrealkv://` connections run the 3.2 engine and pick up everything that landed in 3.1 and 3.2. The native glue moved with the `RpcProtocol` trait: its session map is now keyed by a concrete `Uuid` rather than `Option<Uuid>`, so the embedded connection's single implicit session is registered under a generated id and every request without a session id routes to it. Behaviour is unchanged - the embedded connection has never supported `attach`/`detach` or client-side transactions, and `use`/`signin` state still persists across calls on a connection. CBOR request decoding now bounds nesting with the datastore's `max_object_parsing_depth` (default 100), matching what the server applies to its own parsers.
- Refreshed the rest of the dependency surface: every pinned GitHub Actions workflow dependency moved to its current release, the Python lockfile moved to current (notably `mypy` 2.3.0 and `ruff` 0.16.2), and the CI/docker-compose SurrealDB server versions moved to the latest patch of each series already covered (`v2.1.9`, `v3.0.5`). `aiohttp` stays capped below 3.14 for resolution only - `aioresponses` 0.7.9 still cannot construct 3.14's `ClientResponse` - and the cap remains absent from published wheel metadata.

### Added
- A Dependabot configuration covering GitHub Actions, the `uv` Python lockfile, and the embedded extension's Cargo manifest, so these no longer drift silently between releases. `surrealdb-core` and `surrealdb-types` are excluded from the grouped Rust updates: a bump there decides which SurrealDB engine the embedded wheel ships and has changed the `RpcProtocol` trait within a minor release, so each gets its own reviewable pull request.

## [3.0.0-beta.1] - 2026-08-09

First beta on the 3.0.0 track. The v3 API surface settled over the alpha series is now considered feature-complete, and this release closes the last two gaps in it: every failure the SDK raises is a `SurrealError`, and the session/transaction wrappers expose the full connection RPC set. Both packages move to the `Development Status :: 4 - Beta` classifier.

### Added
- `TransportError`, a new branch of the error hierarchy for failures that produced no structured server response, alongside the existing `ServerError` branch. `ConnectionUnavailableError` now derives from it, joined by `TransportTimeoutError` (the request timed out) and `HttpStatusError` (a non-2xx HTTP response, carrying `.status`, `.body`, and `.url`). The split is what retry logic keys on: a `TransportError` may succeed if retried, a `ServerError` describes a decision the server already made.
- `query_raw()`, `info()`, and `version()` on the session and transaction wrapper classes (`AsyncSurrealSession` / `BlockingSurrealSession`, `AsyncSurrealTransaction` / `BlockingSurrealTransaction`). These were the only connection RPCs missing from the wrappers, so calling `session.query_raw(...)` raised `AttributeError` even though the underlying connection method already accepted `session_id` / `txn_id`. Each forwards the session (and, on a transaction, the txn) like every other wrapper method.

### Fixed
- Transport failures no longer escape as third-party exceptions, so `except SurrealError` now reliably covers every failure the SDK raises. Previously the exception type depended on how a failure was represented: an RPC error in a 2xx body became a `ServerError`, but a non-2xx `/rpc` response leaked `requests.exceptions.HTTPError` or `aiohttp.ClientResponseError`, an unreachable host leaked `requests.exceptions.ConnectionError` / `aiohttp.ClientConnectorError` / `ConnectionRefusedError`, and an undecodable body leaked a CBOR decode error. All four transports (blocking/async, HTTP/WebSocket) now map these to `HttpStatusError`, `ConnectionUnavailableError`, `TransportTimeoutError`, or `UnexpectedResponseError`, each preserving the original exception as `__cause__`. A non-2xx response whose body *does* contain a structured RPC error still maps to its `ServerError` subclass.

### Changed
- Both `surrealdb` and `surrealdb-embedded` now declare `Development Status :: 4 - Beta` instead of `3 - Alpha`. Packaging metadata only; no code changes.

## [3.0.0-alpha.4] - 2026-07-16

### Security
- Bump the embedded extension's `pyo3` to 0.29.0 (and `pyo3-async-runtimes` to 0.29), fixing a high-severity out-of-bounds read in `PyList` / `PyTuple` iterators and a missing `Sync` bound on `PyCFunction::new_closure`. Affects the native `surrealdb-embedded` package only; no API changes.

## [3.0.0-alpha.3] - 2026-07-16

Follow-up to `3.0.0-alpha.2`: adds the `into=` row-model API, fixes session authentication propagation, aligns `delete` with `select`, and re-enables mypy type-checking on the test suite.

### Added
- Keyword-only `into=` argument on `select`, `create`, `update`, `upsert`, `delete`, and `insert` (async and sync, including the session/transaction wrappers) mapping each returned record onto a model class — a dataclass, a pydantic `BaseModel`, or any class accepting the record's fields as keyword arguments. Return types are narrowed precisely per `@overload`: a single-record target resolves to `Model` (or `Model | None`), a `Table` target to `list[Model]`. The no-data builder forms (`create(record, into=Model)`, `update(record, into=Model)`, `insert(table, into=Model)`) carry the model through their clause methods (`.content` / `.merge` / … / `.execute`). Mapping reuses the existing `_map_to_class` helper.
- `query(sql).into(Model, rows=True)` maps each **row** of a single statement's result onto `Model`, returning `list[Model]`. The default `.into(cls)` (statements-to-fields) behaviour is unchanged when `rows` is not set.

### Changed
- `delete(RecordID)` now returns `dict | None` (the deleted record, or `None` when absent), matching `select`; `delete(Table)` still returns a list.
- Internal: the test suite is now type-checked by CI (`mypy tests/`) with the full set of error codes enabled, so it guards against public-API type regressions. Only `index`, `union-attr`, and `call-overload` remain suppressed for tests, because the public `Value` union is indexed into pervasively across the suite with no bug-catching value.

### Fixed
- `new_session()` now propagates the connection's authentication to the new session, so session-scoped operations run with the connection's identity. Previously a freshly attached session was unauthenticated and its writes silently no-opped (the server returned an empty result with no error). `authenticate()` also records the connection's token so it can be replayed.

## [3.0.0-alpha.2] - 2026-07-16

Follow-up to `3.0.0-alpha.1` that finalises the v3 API surface and fixes a batch of issues found in review.

### Added
- `RecordID`, `Table`, `Duration`, `Range`, and all `Geometry` types are now hashable, so they can be used as `dict` keys and `set` members.
- `Datetime` gained `__eq__`, `__repr__`, and `__hash__`, making it a proper value type.
- `.first()` on the query builder (async coroutine / sync method), returning the first statement's result, or `None` when there are no statements.
- Exported `AsyncSurrealConnection` and `BlockingSurrealConnection` union type aliases for annotating connection instances.
- HTTP connections implement `close()` and reuse a single pooled session across requests within a context manager.
- README "Live queries" section documenting `live()` / `subscribe_live()` / `kill()`, and a pointer to the Spectron client.
- Docstrings on the public CRUD / query / select / live-query methods.

### Changed
- **Breaking:** Sync `select`, `create`, `update`, `upsert`, `delete`, and `insert` are now **eager**. `select(...)` and `delete(...)` run immediately and return the result. `create/update/upsert(record, data)` and `insert(table, data)` run immediately and return the result; the no-data form (`create(record)`, `insert(table)`) returns a builder whose clause methods (`.content` / `.replace` / `.merge` / `.patch` / `.relation`) and `.execute()` run the operation and return the result. This removes the sync magic-consumption footguns (`bool()`, `==`, indexing, `__getattr__`) present in alpha.1.
- **Breaking:** Sync builders no longer implement any auto-executing magic methods (`__bool__`, `__eq__`, `__getitem__`, `__iter__`, `__len__`, `__contains__`, `__getattr__`, and the pending-`repr`/`str`). Inspecting a builder never triggers a query or mutation.
- **Breaking:** `query()` now **always** returns a `list[Value]` (one entry per statement) — even for a single statement — for both async (`await db.query(...)` / `.execute()`) and sync (`.execute()`). This supersedes the alpha.1 "single `Value` for one statement, `tuple` for many" behaviour. Use `.first()` for the first statement's result.
- **Breaking:** `select(RecordID)` (or a single `"table:id"` string) now returns `dict[str, Value] | None` (the record, or `None` when it is absent) instead of a single-element list; `select(Table)` (or a bare table name) still returns `list[Value]`. `select()` is now typed via `@overload` on the templates, all four connections, and the session/transaction classes.
- **Breaking:** The Spectron client is no longer re-exported from the top-level `surrealdb` package; import it from `surrealdb.spectron` (`from surrealdb.spectron import Spectron, AsyncSpectron`). This keeps the Spectron surface out of the core SDK's stability guarantee.
- **Breaking:** `query_raw`'s bound-variable keyword argument is renamed from `params` to `vars`, matching `query`.
- The session and transaction wrapper classes now carry the same CRUD `@overload` precision as the base connection.
- Python `set` / `frozenset` now encode with SurrealDB's set tag (56) instead of the generic CBOR set tag (258).
- `info()`'s record-auth `$auth` fallback is now applied consistently across all four transports and keyed on the structured error kind rather than the error-message text.

### Removed
- **Breaking:** The low-level `TAG_*` CBOR constants are no longer exported from the top-level `surrealdb` package; they remain available at `surrealdb.data.types.constants`.
- Removed the unused `AsyncSurrealDBMeta` / `BlockingSurrealDBMeta` metaclasses and the dead duplicate `surrealdb.cbor` shim modules (`decoder`, `encoder`, `types`, `tool`).

### Fixed
- `RecordID.parse` (and `table_or_record_id`) no longer raise on record ids containing `:` (e.g. `"user:complex:id"`).
- WebSocket live queries: `subscribe_live` generators are woken and cleaned up on `kill()` / `close()` instead of leaking; a mid-request disconnect raises a typed `ConnectionUnavailableError` instead of a bare `KeyError`; the blocking client correlates RPC replies by id (never returning a live notification as an RPC result), reads under its lock, and logs via `logging` instead of `print`.
- Removed several unreachable encoder branches and a stale decoder `TODO` in the CBOR layer.

## [3.0.0-alpha.1] - 2026-07-13
### Added
- New awaitable / lazy CRUD builder pattern. `create`, `update`, `upsert`, `delete`, and `insert` now return a builder that exposes chainable clause methods (`.content` / `.replace` / `.merge` / `.patch`) and is awaitable (async) or auto-executing on consumption (sync).
- `.insert(table, data, relation=True)` (and the equivalent `.insert(table).relation().content(data)` chain) replaces the standalone `insert_relation` method.
- New `run(name, args=None, version=None)` method on every connection / session / transaction, wired to the `RUN` RPC method.
- `query().into(cls)` maps the N statement results positionally onto a dataclass (or any class accepting keyword arguments by parameter order).
- New v3 API tests under `tests/unit_tests/connections/v3_api/` covering builder clauses, multi-statement query results, `.into()`, and `run()`.
- Public re-exports of the builder classes (`AsyncCrudBuilder`, `AsyncInsertBuilder`, `AsyncQueryBuilder`, `AsyncQueryIntoBuilder`, and the `Sync*` equivalents) from `surrealdb`.
- `QueryError.is_transaction_conflict` property, detecting `TRANSACTION_CONFLICT` query errors (#268).
- `__str__` methods for `Datetime`, `Duration`, and all 7 `Geometry` classes, rendering SurrealQL literals instead of Python's default `repr` (#270).
- Export `escape_identifier` from the top-level `surrealdb` package and document `RecordID.id`'s raw (unescaped) contract (#271).

### Changed
- **Breaking:** `query()` now surfaces every statement result. A single-statement query returns the result `Value`; a multi-statement query (or `BEGIN ... COMMIT` block) returns `tuple[Value, ...]`. Fixes the silent-discard behaviour reported in [#232](https://github.com/surrealdb/surrealdb.py/issues/232).
- **Breaking:** Sync `query()` / CRUD methods return a lazy builder. The operation runs when the result is consumed (indexed, iterated, compared, printed, etc.) or when `.execute()` is called explicitly. Fire-and-forget statements like `db.query("DELETE foo")` must call `.execute()` to run.
- **Breaking:** `create`, `update`, `upsert`, `delete`, and `insert` are typed via `@overload` so type checkers infer `dict[str, Value]` for `RecordID` targets and `list[Value]` for `Table` targets.
- **Breaking:** Raw-string resource targets are now strictly validated against the safe-identifier pattern (`[A-Za-z_][A-Za-z0-9_]*`). Names with hyphens or other special characters must be wrapped in `Table(...)` or `RecordID(...)` so the SDK can safely route them through parameter binding (CRUD ops use `type::table($var)`) or SurrealQL's `⟨...⟩` escape (`INSERT`, where the server doesn't accept `type::table()`).
- The session and transaction classes (`AsyncSurrealSession` / `BlockingSurrealSession`, `AsyncSurrealTransaction` / `BlockingSurrealTransaction`) expose the same builder API and forward `session_id` / `txn_id` through to every operation.

### Removed
- **Breaking:** `db.merge(record, data)` — use `db.update(record).merge(data)` (or `.create/.upsert(record).merge(data)`).
- **Breaking:** `db.patch(record, data)` — use `db.update(record).patch(data)`.
- **Breaking:** `db.insert_relation(table, data)` — use `db.insert(table, data, relation=True)` or `db.insert(table).relation().content(data)`.

### Fixed
- Restored the record-level auth fallback in `BlockingHttpSurrealConnection.info()`. When the server returned `No result found` from `INFO` (record-auth scenario), the SDK now retries via `SELECT * FROM $auth` and returns the resolved record; the fallback was inadvertently dead in the initial v3 builder migration because `query()` returns a lazy builder.
- `Range.__str__` producing invalid SurrealQL (#269).

## [2.0.1]
### Changed
- **Breaking:** WebSocket `subscribe_live()` now yields the full live-notification object (`action`, `result`, `id`, …) from the server instead of only the inner record ([#247](https://github.com/surrealdb/surrealdb.py/issues/247)).

### Fixed
- `subscribe_live` WebSocket tests perform mutations on a secondary connection so query RPC replies are not interleaved with live notifications on the same socket.

## [2.0.0] - 2026-04-23
### Added
- Support `surrealkv+versioned://` URL scheme for embedded databases with versioning (#231).

## [2.0.0-alpha.1] - 2026-02-25
### Added
- SurrealDB 3.x protocol and feature support (#230).
- Structured error hierarchy and `ServerError` with SurrealDB 3.x–style kind/details (#233).
- Logfire observability example and README section (#229).

### Changed
- Drop Python 3.9 support; minimum Python is 3.10 (#230).
- Add release-comment workflow for builds (#240).

### Fixed
- Fix WebSocket session and transaction ID handling for `begin`/`commit`/`cancel` (#236).

## [1.0.8] - 2026-01-07
### Added
- Add optional `pydantic` extra so `RecordID` fields validate and serialize cleanly in `BaseModel`s and JSON schema outputs.

### Changed
- Changed `cerberus` for `pydantic-core`.

### Fixed
- Improve build stability and ensure `musl-tools` is installed for Linux builds.

## [1.0.7] - 2025-12-03
### Added
- Support compound duration parsing in `Duration.parse`.
- Provide native embedded database support.
- Add comprehensive framework integration examples.
- Introduce `pyright` checks and additional data type coverage.
- Expand test coverage for record IDs and Cursor tooling rules.

### Changed
- Simplify database method return types to `Value`.
- Issue text-based queries instead of using v1 RPC methods.

### Fixed
- Correct Duration encoding and decoding.
- Enforce GeoJSON-compliant closed linear rings in `GeometryPolygon`.
- Escape string identifiers in `RecordID` to match SurrealDB behavior.
- Fix `decimal.Decimal` encoding.
- Address race condition in concurrent environments.
- Apply formatting, linting, and test stability fixes.

## [1.0.6] - 2025-07-21
### Changed
- Switch project management to `uv` and simplify the developer environment.

## [1.0.5] - 2025-07-18
### Changed
- Streamline CI/build workflows and improve developer tooling.

## [1.0.4] - 2025-05-21
### Added
- Add decimal support and CBOR integration improvements.

### Fixed
- Improve polygon handling and async WebSocket error handling.
- Fix `None` encoding/decoding for SurrealDB v2.2.x and later.
- Correct timezone offset decoding and types in connections.
- Normalize error response handling.

## [1.0.3] - 2025-02-04
### Fixed
- Correct datetime tagging.

## [1.0.2] - 2025-02-02
### Changed
- Update project metadata.

### Fixed
- Remove WebSocket max message size limit.

## [1.0.1] - 2025-02-01
### Fixed
- Resolve signup/signin issues and improve CI/test stability.

## [1.0.0] - 2025-01-30
### Added
- Initial stable release of the SurrealDB Python client.

[Unreleased]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-beta.8...HEAD
[3.0.0-beta.8]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-beta.7...v3.0.0-beta.8
[3.0.0-beta.7]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-beta.6...v3.0.0-beta.7
[3.0.0-beta.6]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-beta.5...v3.0.0-beta.6
[3.0.0-beta.5]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-beta.4...v3.0.0-beta.5
[3.0.0-beta.4]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-beta.3...v3.0.0-beta.4
[3.0.0-beta.3]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-beta.2...v3.0.0-beta.3
[3.0.0-beta.2]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-beta.1...v3.0.0-beta.2
[3.0.0-beta.1]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-alpha.4...v3.0.0-beta.1
[3.0.0-alpha.4]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-alpha.3...v3.0.0-alpha.4
[3.0.0-alpha.3]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-alpha.2...v3.0.0-alpha.3
[3.0.0-alpha.2]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-alpha.1...v3.0.0-alpha.2
[3.0.0-alpha.1]: https://github.com/surrealdb/surrealdb.py/compare/v2.0.1...v3.0.0-alpha.1
[2.0.1]: https://github.com/surrealdb/surrealdb.py/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/surrealdb/surrealdb.py/compare/v2.0.0-alpha.1...v2.0.0
[2.0.0-alpha.1]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.8...v2.0.0-alpha.1
[1.0.8]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.0...v1.0.1
