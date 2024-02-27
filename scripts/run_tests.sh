#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..

#CONNECTION_PORT

# testing all the http async and blocking for last three versions
export CONNECTION_PROTOCOL="http"
python -m unittest discover
export CONNECTION_PORT="8121"
python -m unittest discover
export CONNECTION_PORT="8120"
python -m unittest discover
export CONNECTION_PORT="8101"
python -m unittest discover
export CONNECTION_PORT="8111"
python -m unittest discover

# testing all the ws async and blocking for last three versions
export CONNECTION_PROTOCOL="ws"
export CONNECTION_PORT="8000"
python -m unittest discover
export CONNECTION_PORT="8121"
python -m unittest discover
export CONNECTION_PORT="8120"
python -m unittest discover
export CONNECTION_PORT="8101"
python -m unittest discover
export CONNECTION_PORT="8111"
python -m unittest discover
