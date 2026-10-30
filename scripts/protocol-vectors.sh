#!/usr/bin/env bash
# Fetch the CBOR value vectors from a surrealdb-protocol release tag into the
# test suite. They are fetched rather than committed; see conformance/README.md.
# The tag in tests/unit_tests/conformance/vectors/VERSION is the one the tests
# run against; pass a new tag to move to it.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$root/tests/unit_tests/conformance/vectors"
tag="${1:-$(cat "$dest/VERSION")}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$tag" https://github.com/surrealdb/surrealdb-protocol.git "$tmp/protocol"
cp "$tmp/protocol/spec/vectors/cbor.yaml" "$tmp/protocol/spec/vectors/cbor2.yaml" "$dest/"
echo "$tag" >"$dest/VERSION"
echo "Fetched the surrealdb-protocol $tag vectors"
