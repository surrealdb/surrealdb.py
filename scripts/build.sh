#!/bin/bash

set -e

echo "========================================="
echo "Building SurrealDB Python SDK"
echo "========================================="
echo ""
echo "This build includes:"
echo "  • Pure Python code (HTTP/WebSocket)"
echo "  • Embedded database (mem://, file://) [opt-in]"
echo ""

# Install dependencies
uv sync --group dev

echo "Building wheels..."
echo "  - surrealdb (pure-Python)"
uv build --out-dir dist/
echo "  - surrealdb-embedded (Rust extension)"
(cd packages/surrealdb_embedded && uv run maturin build --release --out ../../dist/)

echo ""
echo "✓ Build successful!"
echo ""
echo "Output:"
ls -lh dist/*.whl

echo ""
echo "Wheel size:"
du -h dist/*.whl | tail -1

echo ""
echo "To install (local wheels): uv pip install dist/$(ls dist/*.whl | head -1 | xargs basename)"
