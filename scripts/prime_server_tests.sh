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
refresh_files "integration_tests/flask/app/surreal.py"

# copy package files to flask server test
cp -r surrealdb/ integration_tests/flask/app/surreal.py/surrealdb/
cp -r src/ integration_tests/flask/app/surreal.py/src/
cp -r .cargo/ integration_tests/flask/app/surreal.py/.cargo/

cp Cargo.toml integration_tests/flask/app/surreal.py/Cargo.toml
cp MANIFEST.in integration_tests/flask/app/surreal.py/MANIFEST.in
cp setup.py integration_tests/flask/app/surreal.py/setup.py
cp pyproject.toml integration_tests/flask/app/surreal.py/pyproject.toml

# build flask server with no cache
cd integration_tests/flask/
docker-compose build --no-cache
#docker-compose up -d
#
## wait for server to start
#sleep 5
#
## run tests
#newman
