#!/bin/bash

set -e

echo "========================================="
echo "Building SurrealDB Python SDK"
echo "========================================="
echo ""
echo "This build includes:"
echo "  • Pure Python code (HTTP/WebSocket)"
echo "  • Embedded database (mem://, file://)"
echo ""

# Install dependencies
uv sync --group dev

# Build with maturin
echo "Building wheel (this may take several minutes)..."
uv run maturin build --release --out dist/

echo ""
echo "✓ Build successful!"
echo ""
echo "Output:"
ls -lh dist/*.whl

echo ""
echo "Wheel size:"
du -h dist/*.whl | tail -1

echo ""
echo "To install: uv pip install dist/$(ls dist/*.whl | head -1 | xargs basename)"
echo "Or for development: maturin develop --release"
