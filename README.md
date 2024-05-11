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

View the SDK documentation [here](https://surrealdb.com/docs/integration/libraries/python).

## How to install

```sh
pip install surrealdb
```

## Getting started

### Running within synchronous code

> This example requires SurrealDB to be [installed](https://surrealdb.com/install) and running on port 8000.

Import the SDK and create the database connection:

```python
from surrealdb import SurrealDB

db = SurrealDB("ws://localhost:8000/database/namespace")
```

Here, we can see that we defined the connection protocol as WebSocket using `ws://`. We then defined the host as `localhost` and the port as `8000`.

Finally, we defined the database and namespace as `database` and `namespace`.
We need a database and namespace to connect to SurrealDB. 

Now that we have our connection we need to signin:

```python
db.signin({
    "username": "root",
    "password": "root",
})
```
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

```python
import asyncio
from surrealdb import AsyncSurrealDB

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
    print(outcome)


# Run the main function
asyncio.run(main())
```

### Using Jupyter Notebooks

The Python SDK currently only supports the `AsyncSurrealDB` methods.