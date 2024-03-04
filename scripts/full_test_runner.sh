#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..

docker-compose up -d
sleep 5

python3 -m unittest discover
docker-compose down

# deactivate
# rm -f testvenv
