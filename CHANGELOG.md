# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/surrealdb/surrealdb.py/compare/v3.0.0-alpha.2...HEAD
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
