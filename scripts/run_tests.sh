#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..
cd src
export PYTHONPATH=$(pwd)
cd ..
python -m unittest discover
