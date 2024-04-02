<p align="center">
    <img width="300" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/icon.png" alt="SurrealDB Icon">
</p>

<br>

<p align="center">
    <a href="https://surrealdb.com#gh-dark-mode-only" target="_blank">
        <img width="300" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/white/logo.svg" alt="SurrealDB Logo">
    </a>
    <a href="https://surrealdb.com#gh-light-mode-only" target="_blank">
        <img width="300" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/black/logo.svg" alt="SurrealDB Logo">
    </a>
</p>

<h3 align="center">
    <a href="https://surrealdb.com#gh-dark-mode-only" target="_blank">
        <img src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/white/text.svg" height="15" alt="SurrealDB">
    </a>
    <a href="https://surrealdb.com#gh-light-mode-only" target="_blank">
        <img src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/black/text.svg" height="15" alt="SurrealDB">
    </a>
    is the ultimate cloud <br> database for tomorrow's applications
</h3>

<h3 align="center">Develop easier. &nbsp; Build faster. &nbsp; Scale quicker.</h3>

<br>

<p align="center">
    <a href="https://github.com/surrealdb/surrealdb.py"><img src="https://img.shields.io/badge/status-beta-ff00bb.svg?style=flat-square"></a>
    &nbsp;
    <a href="https://surrealdb.com/docs/integration/libraries/python"><img src="https://img.shields.io/badge/docs-view-44cc11.svg?style=flat-square"></a>
    &nbsp;
    <a href="https://github.com/surrealdb/surrealdb.py"><img src="https://img.shields.io/badge/license-Apache_License_2.0-00bfff.svg?style=flat-square"></a>
    &nbsp;
    <a href="https://twitter.com/surrealdb"><img src="https://img.shields.io/badge/twitter-follow_us-1d9bf0.svg?style=flat-square"></a>
    &nbsp;
    <a href="https://dev.to/surrealdb"><img src="https://img.shields.io/badge/dev-join_us-86f7b7.svg?style=flat-square"></a>
    &nbsp;
    <a href="https://www.linkedin.com/company/surrealdb/"><img src="https://img.shields.io/badge/linkedin-connect_with_us-0a66c2.svg?style=flat-square"></a>
</p>

<p align="center">
	<a href="https://surrealdb.com/blog"><img height="25" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/social/blog.svg" alt="Blog"></a>
	&nbsp;
	<a href="https://github.com/surrealdb/surrealdb"><img height="25" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/social/github.svg" alt="Github	"></a>
	&nbsp;
    <a href="https://www.linkedin.com/company/surrealdb/"><img height="25" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/social/linkedin.svg" alt="LinkedIn"></a>
    &nbsp;
    <a href="https://twitter.com/surrealdb"><img height="25" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/social/twitter.svg" alt="Twitter"></a>
    &nbsp;
    <a href="https://www.youtube.com/channel/UCjf2teVEuYVvvVC-gFZNq6w"><img height="25" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/social/youtube.svg" alt="Youtube"></a>
    &nbsp;
    <a href="https://dev.to/surrealdb"><img height="25" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/social/dev.svg" alt="Dev"></a>
    &nbsp;
    <a href="https://surrealdb.com/discord"><img height="25" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/social/discord.svg" alt="Discord"></a>
    &nbsp;
    <a href="https://stackoverflow.com/questions/tagged/surrealdb"><img height="25" src="https://raw.githubusercontent.com/surrealdb/surrealdb/main/img/social/stack-overflow.svg" alt="StackOverflow"></a>

</p>

# surrealdb.py

The official SurrealDB SDK for Python.

[See the documentation here](https://surrealdb.com/docs/surrealdb/integration/sdks/python) 

## Getting Started
Below is a quick guide on how to get started with SurrealDB in Python.

### Running SurrealDB
Before we can do anything, we need to download SurrealDB and start the server.
[See how to do that here](https://surrealdb.com/docs/surrealdb/installation/)

After we have everything up and running, we can install the Python SDK.

### Installing the Python SDK

```bash
pip install surrealdb
```

### Using the (synchronous) Python methods

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

### Using the async Python methods

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