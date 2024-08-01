<br>

<p align="center">
	<img width=120 src="https://raw.githubusercontent.com/surrealdb/icons/main/surreal.svg" />
	&nbsp;
	<img width=120 src="https://raw.githubusercontent.com/surrealdb/icons/main/python.svg" />
</p>

<h3 align="center">The official SurrealDB SDK for Python.</h3>

<br>

<p align="center">
	<a href="https://github.com/surrealdb/surrealdb.py"><img src="https://img.shields.io/badge/status-beta-ff00bb.svg?style=flat-square"></a>
	&nbsp;
	<a href="https://surrealdb.com/docs/integration/libraries/javascript"><img src="https://img.shields.io/badge/docs-view-44cc11.svg?style=flat-square"></a>
	&nbsp;
	<a href="https://pypi.org/project/surrealdb/"><img src="https://img.shields.io/pypi/v/surrealdb?style=flat-square"></a>
    &nbsp;
    <a href="https://pypi.org/project/surrealdb/"><img src="https://img.shields.io/pypi/dm/surrealdb?style=flat-square"></a>    
	&nbsp;
	<a href="https://pypi.org/project/surrealdb/"><img src="https://img.shields.io/pypi/pyversions/surrealdb?style=flat-square"></a>
</p>

<p align="center">
	<a href="https://surrealdb.com/discord"><img src="https://img.shields.io/discord/902568124350599239?label=discord&style=flat-square&color=5a66f6"></a>
	&nbsp;
    <a href="https://twitter.com/surrealdb"><img src="https://img.shields.io/badge/twitter-follow_us-1d9bf0.svg?style=flat-square"></a>
    &nbsp;
    <a href="https://www.linkedin.com/company/surrealdb/"><img src="https://img.shields.io/badge/linkedin-connect_with_us-0a66c2.svg?style=flat-square"></a>
    &nbsp;
    <a href="https://www.youtube.com/channel/UCjf2teVEuYVvvVC-gFZNq6w"><img src="https://img.shields.io/badge/youtube-subscribe-fc1c1c.svg?style=flat-square"></a>
</p>

# surrealdb.py

The official SurrealDB SDK for Python.

## Documentation

<<<<<<< HEAD
## Getting Started
Below is a quick guide on how to get started with SurrealDB in Python.

### Running SurrealDB
Before we can do anything, we need to download SurrealDB and start the server. The easiest, cleanest way to do this
is with [Docker](https://www.docker.com/) abd [docker-compose](https://docs.docker.com/compose/) with the following
docker-compose file:

```yaml
version: '3'
services:
  surrealdb:
    image: surrealdb/surrealdb
    command: start
    environment:
      - SURREAL_USER=root
      - SURREAL_PASS=root
      - SURREAL_LOG=trace
    ports:
      - 8000:8000
```
Here we are pulling the offical SurrealDB image from Docker Hub and starting it with the `start` command. We are also
setting the environment variables `SURREAL_USER` and `SURREAL_PASS` to `root` and `SURREAL_LOG` to `trace`. This will
allow us to connect to the database with the username `root` and password `root` and will set the log level to `trace`.
Finally, we are exposing port `8000` so we can connect to the database.

Now that we have everything up and running, we can move onto installing the Python library.

### Installing the Python Library

Right now the library is in beta, so you will need to install it from GitHub with Rust installed on your machine
as Rust will be needed to compile part of the library. Installation for Rust can be found 
[here](https://www.rust-lang.org/tools/install). Once Rust is installed, you can install this library with the
following command:

```bash
pip install git+https://github.com/surrealdb/surrealdb.py@rust-no-runtime
```

Installation can take a while as it needs to compile the Rust code. If you want to use the python client in a Docker
build in production you can use a two layered build which will use Rust to compile the library and then copy the
compiled library into a new python image so your production image doesn't need to have Rust installed. Below is an
example of a Dockerfile that will do this for a Flask application:

```dockerfile
FROM rust:latest as builder

RUN apt-get update
RUN apt install python3.9 -y
RUN apt-get install -y python3-dev -y
RUN apt-get install -y python3-pip -y
RUN pip install --upgrade pip setuptools wheel

RUN apt-get install libclang-dev -y

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD . /app

# install the python library locally
RUN pip install ./surreal.py/

# or install the python library from github
RUN pip install git+https://github.com/surrealdb/surrealdb.py@rust-no-runtime

# server build
FROM python:3.9

RUN apt-get update \
    && apt-get install -y python3-dev python3-pip \
    && pip install --upgrade pip setuptools wheel \
    && pip install flask gunicorn

WORKDIR /app

# copy the built python packages from the previous stage to the new image
COPY --from=builder /usr/local/lib/python3.9/dist-packages /usr/local/lib/python3.9/site-packages

# copy the python server app code to the new image
COPY --from=builder /app /app

# Run the python server using gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "--timeout", "900", "main:app"]
```

You can change the python version and the `CMD` could change depending on your application. Now that we have our
python application installing and running with SurrealDB, we can move onto using the python library.

### Using the blocking Python Library

We can then import the library and create the connection with the following code:
=======
View the SDK documentation [here](https://surrealdb.com/docs/integration/libraries/python).

## How to install

```sh
pip install surrealdb
```

## Getting started

### Running within synchronous code

> This example requires SurrealDB to be [installed](https://surrealdb.com/install) and running on port 8000.

Import the SDK and create the database connection:
>>>>>>> ffefd8a2354ff597f6f18115d18fa4eab45d6540

```python
from surrealdb import SurrealDB

<<<<<<< HEAD
connection = SurrealDB("ws://localhost:8000/database/namespace")
```
Here, we can see that we defined the connection protocol as websocket using `ws://`. We then defined the host as
`localhost` and the port as `8000`. Finally, we defined the database and namespace as `database` and `namespace`.
We need a database and namespace to connect to SurrealDB. 

Now that we have our connection we need to signin using with the following code:

```python
connection.signin({
=======
db = SurrealDB("ws://localhost:8000/database/namespace")
```

Here, we can see that we defined the connection protocol as WebSocket using `ws://`. We then defined the host as `localhost` and the port as `8000`.

Finally, we defined the database and namespace as `database` and `namespace`.
We need a database and namespace to connect to SurrealDB. 

Now that we have our connection we need to signin:

```python
db.signin({
>>>>>>> ffefd8a2354ff597f6f18115d18fa4eab45d6540
    "username": "root",
    "password": "root",
})
```
<<<<<<< HEAD
For our getting started example we are now going to run some simple raw SurrealQL queries to create some users and
then select them. We can then print the outcome of the query with the following code:

```python
connection.query("CREATE user:tobie SET name = 'Tobie';")
connection.query("CREATE user:jaime SET name = 'Jaime';")
outcome = connection.query("SELECT * FROM user;")
print(outcome)
```

This will give you the following JSON output:

```json
[
    {
        "id": "user:jaime",
        "name": "Jaime"
    },
    {
        "id": "user:tobie",
        "name": "Tobie"
    }
]
```

### Using the async Python Library

We can then import the library and create the connection with the following code:

```python
from surrealdb import AsyncSurrealDB

connection = AsyncSurrealDB("ws://localhost:8000/database/namespace")
await connection.connect()
```

Essentially the interface is exactly the same however, the functions are async. Below is a way to run the async code:
=======
We can now run our queries to create some users, select them and print the outcome.

```python
db.query("CREATE user:tobie SET name = 'Tobie';")
db.query("CREATE user:jaime SET name = 'Jaime';")
outcome = db.query("SELECT * FROM user;")
print(outcome)
```

### Running within asynchronous code

> This example requires SurrealDB to be [installed](https://surrealdb.com/install) and running on port 8000.

The async methods work in the same way, with two main differences:
- Inclusion of `async def / await`.
- You need to call the connect method before signing in.
>>>>>>> ffefd8a2354ff597f6f18115d18fa4eab45d6540

```python
import asyncio
from surrealdb import AsyncSurrealDB
<<<<<<< HEAD


async def main():
    connection = AsyncSurrealDB("ws://localhost:8000/database/namespace")
    await connection.connect()
    await connection.signin({
        "username": "root",
        "password": "root",
    })
    await connection.query("CREATE user:tobie SET name = 'Tobie';")
    await connection.query("CREATE user:jaime SET name = 'Jaime';")
    outcome = await connection.query("SELECT * FROM user;")
=======

async def main():
    db = AsyncSurrealDB("ws://localhost:8000/database/namespace")
    await db.connect()
    await db.signin({
        "username": "root",
        "password": "root",
    })
    await db.query("CREATE user:tobie SET name = 'Tobie';")
    await db.query("CREATE user:jaime SET name = 'Jaime';")
    outcome = await db.query("SELECT * FROM user;")
>>>>>>> ffefd8a2354ff597f6f18115d18fa4eab45d6540
    print(outcome)


# Run the main function
asyncio.run(main())
```

### Using Jupyter Notebooks

The Python SDK currently only supports the `AsyncSurrealDB` methods.