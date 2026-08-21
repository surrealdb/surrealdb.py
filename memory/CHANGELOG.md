# Changelog

All notable changes to `surrealdb-memory` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This package is versioned **independently of the `surrealdb` SDK**. The SDK's
`[memory]` extra depends on it with a `>=` floor, so a release here needs no SDK
release, and vice versa. Releases are cut from a `memory-v<version>` tag; a
plain `v<version>` tag releases the SDK and leaves this package alone.

## [Unreleased]

## [1.0.0-beta.1] - 2026-08-16

First release as a separate distribution. The code is not new — it shipped
inside the SDK as `surrealdb.spectron` through eleven 3.0.0 pre-releases — but
this is the first version of it with a version number of its own.

### Changed

- Installed as `pip install 'surrealdb[memory]'` and imported as
  `from surrealdb.memory import Memory`. Previously it arrived with every
  `surrealdb` install, whether or not it was wanted, and its version *was* the
  SDK's.
- Product names are gone from the API. `Spectron` and `AsyncSpectron` are
  `Memory` and `AsyncMemory`. `SpectronError`, `SpectronAPIError`,
  `SpectronAuthError`, `SpectronNotFoundError` and `SpectronScopeError` are
  `MemoryServiceError`, `MemoryAPIError`, `MemoryAuthError`,
  `MemoryNotFoundError` and `MemoryScopeError`.

  The base error is `MemoryServiceError` and not `MemoryError` because
  `MemoryError` is a Python builtin. Shadowing it would mean a caller's
  `except MemoryError:` no longer catches an interpreter out-of-memory, while a
  real service failure goes uncaught by code expecting the builtin — the two
  classes are unrelated, so both directions fail silently.

- The module path is `surrealdb_memory`. `surrealdb.memory` remains the
  supported spelling, forwarded by a small module in the SDK.

Migrating is two substitutions:

```python
# before
from surrealdb.spectron import Spectron, AsyncSpectron, SpectronError
# after — pip install 'surrealdb[memory]'
from surrealdb.memory import Memory, AsyncMemory, MemoryServiceError
```

[Unreleased]: https://github.com/surrealdb/surrealdb.py/compare/memory-v1.0.0-beta.1...HEAD
[1.0.0-beta.1]: https://github.com/surrealdb/surrealdb.py/releases/tag/memory-v1.0.0-beta.1
