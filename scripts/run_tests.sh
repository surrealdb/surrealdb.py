#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..


export CONNECTION_PROTOCOL="http"
python -m unittest discover

export CONNECTION_PROTOCOL="ws"
python -m unittest discover