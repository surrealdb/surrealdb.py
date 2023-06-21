#!/usr/bin/env bash

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH
cd ..

# wipes existing files and creates new ones
refresh_files() {
  local file_path="$1"

  if [ -d "$file_path" ]; then
    echo "Deleting $file_path..."
    rm -rf "$file_path"
    echo "File deleted successfully."
  else
    echo "$file_path does not exist."
  fi

  mkdir "$file_path"
}

# wipe files for servers
refresh_files "server_tests/flask/app/surreal.py"

# copy package files to flask server test
cp -r surrealdb/ server_tests/flask/app/surreal.py/surrealdb/
cp -r src/ server_tests/flask/app/surreal.py/src/
cp -r .cargo/ server_tests/flask/app/surreal.py/.cargo/

cp Cargo.toml server_tests/flask/app/surreal.py/Cargo.toml
cp MANIFEST.in server_tests/flask/app/surreal.py/MANIFEST.in
cp setup.py server_tests/flask/app/surreal.py/setup.py
cp pyproject.toml server_tests/flask/app/surreal.py/pyproject.toml

# build flask server with no cache
cd server_tests/flask/
docker-compose build --no-cache
docker-compose up
docker-compose down
