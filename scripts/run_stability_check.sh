#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..

if [ -d ./logs ]; then
  echo "log directory exists being removed"
  rm -rf ./logs
fi

mkdir logs

# Install dependencies
uv sync --group dev

# Run checks
uv run ruff check src/ > ./logs/ruff_check.log
uv run ruff format src/
uv run ruff format --check --diff src/ > ./logs/ruff_format_check.log
uv run mypy --explicit-package-bases src/ > ./logs/mypy_check.log