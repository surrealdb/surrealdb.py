#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

# Go to project root
cd ..

# Define the PYTHONPATH for the terminal session
export PYTHONPATH=$(pwd)/src

echo "Setting up development environment with uv..."

# Install dependencies with uv (this will create .venv automatically)
uv sync --group dev

echo "Activating uv environment..."
echo "PYTHONPATH is set to: $PYTHONPATH"
echo "You can now run:"
echo "  uv run python <script>"
echo "  uv run ruff check src/"
echo "  uv run mypy src/"
echo "  uv run python -m unittest discover -s tests"
echo ""
echo "Or activate the environment manually with:"
echo "  source .venv/bin/activate"
echo ""
echo "Execute 'exit' to exit the terminal session"

# Start shell with uv environment activated
source .venv/bin/activate
bash --norc
