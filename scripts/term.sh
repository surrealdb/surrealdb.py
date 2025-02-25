#!/usr/bin/env bash

# navigate to directory
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH

# Define the PYTHONPATH for the terminal session
cd ../src
export PYTHONPATH=$(pwd)
cd ..

# Configure the virtual environment if needed
if [ -d "venv" ]; then
  echo "existing python virtual environment exists."
else
  echo "python virtual environment does not exist. Creating one"
  python3 -m venv venv
fi

# start the terminal session
source venv/bin/activate
pip install -r requirements.txt
echo "now running in virtual environment. Execute the 'exit' to exit the virtual env terminal"
bash --norc
