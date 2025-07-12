#!/bin/bash

# Run tests with coverage reporting
# Usage: ./scripts/run_tests_with_coverage.sh [test_path]

set -e

# Default to running all tests if no path specified
TEST_PATH="${1:-tests/}"

echo "Running tests with coverage: $TEST_PATH"
echo "========================================"

# Run pytest with coverage
uv run pytest \
    --cov=src/surrealdb \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-fail-under=60 \
    "$TEST_PATH"

echo ""
echo "Coverage report generated in htmlcov/index.html"
echo "Open htmlcov/index.html in your browser to view detailed coverage" 