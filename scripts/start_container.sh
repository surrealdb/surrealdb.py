#!/bin/bash

# Define Docker Socket
DOCKER_SOCKET="/var/run/docker.sock"

# Container Configuration in JSON
CONTAINER_JSON='{
    "Image": "surrealdb/surrealdb:v1.2.1",
    "Cmd": ["start"],
    "Env": [
        "SURREAL_USER=root",
        "SURREAL_PASS=root",
        "SURREAL_LOG=trace"
    ],
    "HostConfig": {
        "PortBindings": {
            "8000/tcp": [{
                "HostPort": "8121"
            }]
        }
    }
}'

# Create and start the container
RESPONSE=$(curl --unix-socket $DOCKER_SOCKET -X POST \
    -H "Content-Type: application/json" \
    -d "$CONTAINER_JSON" \
    http://localhost/v1.41/containers/create?name=surrealdb_121)

# Check if container creation was successful and extract the container ID
CONTAINER_ID=$(echo $RESPONSE | jq -r .Id)
if [[ $CONTAINER_ID == null ]]; then
    echo "Failed to create container"
    echo "$RESPONSE"
    exit 1
else
    echo "Container created with ID: $CONTAINER_ID"
    echo "$RESPONSE"
fi

# Start the container
curl --unix-socket $DOCKER_SOCKET -X POST \
    http://localhost/v1.41/containers/$CONTAINER_ID/start

echo "Container started"
