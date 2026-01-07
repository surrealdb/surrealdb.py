# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.7...HEAD
[1.0.7]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/surrealdb/surrealdb.py/compare/v1.0.0...v1.0.1
