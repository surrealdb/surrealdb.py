#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

cd ..

if [ -d "./db_snapshots/big_data_snapshot" ]; then
  echo "removing the big data snapshot"
  rm -rf ./db_snapshots/big_data_snapshot
fi

dockpack pull -i maxwellflitton/surrealdb-data -d ./db_snapshots/big_data_snapshot
#rm ./db_snapshots/big_data_snapshot/package/LOCK

docker build -f ./builds/big_data_dockerfile -t surrealdb-big-data .
