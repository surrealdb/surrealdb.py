#!/usr/bin/env bash

# Install dependencies
uv sync --group dev

# Run checks
uv run ruff check src/
uv run ruff format --check --diff src/
uv run mypy --explicit-package-bases src/
uv run mypy --explicit-package-bases tests/
uv run pyright