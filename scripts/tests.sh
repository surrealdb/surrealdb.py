#!/usr/bin/env bash

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/surrealdb --cov-report=term-missing --cov-report=html
