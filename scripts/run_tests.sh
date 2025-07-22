#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..
cd src
export PYTHONPATH=$(pwd)
cd ..

# Run tests with coverage
pytest --cov=src/surrealdb --cov-report=term-missing --cov-report=html
