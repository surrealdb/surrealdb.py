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

ruff check src/ > ./logs/ruff_check.log
black src/
black --check --verbose --diff --color src/ > ./logs/black_check.log
mypy --explicit-package-bases src/ > ./logs/mypy_check.log