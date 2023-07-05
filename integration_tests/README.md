# Server Tests
This section handles the testing of the SurrealDB python client in servers as they would work in
production. The tests are run in a docker container to ensure that the tests are run in a clean
environment.

## Configuring Tests
Tests are built by running the `scripts/prime_server_tests.sh` script. This script will wipe any
existing code and copy over the files needed to install and run the SurrealDB rust python client.
Once everything is copied over the `scripts/prime_server_tests.sh` script will build the python
server with the SurrealDB client with no caches alongside a SurrealDB database instance. 
