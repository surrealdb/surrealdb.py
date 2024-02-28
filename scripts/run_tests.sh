#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..

#CONNECTION_PORT

export PYTHONPATH="."
python tests/scripts/runner.py
