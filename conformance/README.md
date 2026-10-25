# Conformance

This SDK runs the shared SurrealDB SDK conformance suite from
[surrealdb-protocol](https://github.com/surrealdb/surrealdb-protocol), at the
release named in `tests/unit_tests/conformance/vectors/VERSION`.

- **CBOR value vectors.** `tests/unit_tests/conformance/` runs the protocol's
  `spec/vectors/cbor.yaml` and `cbor2.yaml` against the codec, over plain
  `cbor` and over `cbor.2`. `scripts/protocol-vectors.sh` fetches them from
  the release in `VERSION`, and the tests skip until it has. Pass a tag to move
  to another release. The vectors are fetched rather than committed while
  surrealdb-protocol releases are licensed BUSL-1.1.
- **Scenarios.** `driver.py` maps the runner's ops onto the SDK's async API.
  CI runs it in the `conformance` job. Ops without an SDK API answer
  `Unsupported`, which the runner reports as a skip.

To run the scenarios locally, from a checkout of surrealdb-protocol at that
tag, with [Bun](https://bun.sh) and a `surreal` binary:

```bash
bun install
SURREAL_BIN=/path/to/surreal PYTHONPATH=/path/to/surrealdb.py/src:/path/to/surrealdb.py \
  bun conformance/runner/cli.ts --driver "uv run --project /path/to/surrealdb.py python /path/to/surrealdb.py/conformance/driver.py"
```

Set `SURREAL_URL` instead of `SURREAL_BIN` to use a server that is already
running; scenarios that need their own server flags then skip.
