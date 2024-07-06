#!/bin/bash

pip install -r requirements.txt -r dev_requirements.txt -e . docker&
cargo build&

wait

echo "Setup completed"
