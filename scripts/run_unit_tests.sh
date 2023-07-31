#!/usr/bin/env bash

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd $SCRIPTPATH
cd ..

#python -m unittest discover -s unit_tests -p 'test_*.py'
python -m coverage run -m unittest discover -s unit_tests -p 'test_*.py'
