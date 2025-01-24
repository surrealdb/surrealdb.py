#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..
cd tests

if [ -d "./db_snapshots" ];  then
  echo "DB snapshots are already present"
  rm -rf ./db_snapshots
fi

dockpack pull -i maxwellflitton/surrealdb-data -d ./db_snapshots
