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

## Basic Usage
> All examples assume SurrealDB is [installed](https://surrealdb.com/install) and running on port 8000.
### Initialization
To start using the database, create an instance of SurrealDB, connect to your SurrealDB server, and specify the
namespace and database you wish to work with.
```python
from surrealdb import SurrealDB

# Connect to the database
db = SurrealDB(url="ws://localhost:8080")
db.connect()
db.use("namespace", "database_name")
```

### Using context manager
The library supports Python’s context manager to manage connections automatically. 
This ensures that connections are properly closed when the block of code finishes executing.
```python
from surrealdb import SurrealDB

with SurrealDB(url="ws://localhost:8080") as db:
    db.use("namespace", "database_name")
```

### Using Async
The AsyncSurrealDB supports asynchronous operations while retaining compatibility with synchronous workflows, 
ensuring flexibility for any range of use cases. The APIs do not differ 
```python
from surrealdb import AsyncSurrealDB

async with AsyncSurrealDB(url="ws://localhost:8080") as db:
    await db.use("namespace", "database_name")
```
Without context manager:
```python
from surrealdb import AsyncSurrealDB

# Connect to the database
db = AsyncSurrealDB(url="ws://localhost:8080")
await db.connect()
await db.use("namespace", "database_name")
```

### Example Usage
```python
from surrealdb import SurrealDB, GeometryPoint, Table

with SurrealDB(url="ws://localhost:8000") as db:
    db.use("test_ns", "test_db")
    auth_token = db.sign_in(username="root", password="root")

    # Check token validity. This is not necessary if you called `sign_in` before. This authenticates the
    # `db` instance too if `sign_in` was not previously called
    db.authenticate(auth_token)

    # Create an entry
    person = db.create(Table("persons"), {
        "Name": "John",
        "Surname": "Doe",
        "Location": GeometryPoint(-0.11, 22.00),
    })

    print("Created person with a map:", person)

    # Get entry by Record ID
    person = db.select(person.get("id"))
    print("Selected a person by record id: ", person)

    # Or retrieve the entire table
    persons = db.select(Table("persons"))
    print("Selected all in persons table: ", persons)

    # Delete an entry by ID
    _ = db.delete(persons[0].get("id"))

    # Delete all entries
    _ = db.delete(Table("persons"))

    # Confirm empty table
    persons = db.select(Table("persons"))
    print("No Selected person: ", persons)

    # And later, we can invalidate the token
    db.invalidate(auth_token)
```

## Connection Engines
There are 3 available connection engines you can use to connect to SurrealDb backend. It can be via Websocket, HTTP or
through embedded database connections. The connection types are simply determined by the url scheme provided in 
the connection url.

### Via Websocket
Websocket url can be `ws` or `wss` for secure connection. For example `ws://localhost:8000` and `wss://localhost:8000`.
All functionalities are available via websockets.

### Via HTTP
HTTP url can be `http` or `https` for secure connection. For example `http://localhost:8000` and `https://localhost:8000`.
There are some functions that are not available on RPC when using HTTP but are on Websocket. This includes all 
live query/notification methods.


### Using SurrealKV and Memory
SurrealKV and In-Memory also do not support live notifications at this time. This would be updated in a later 
release.

For Surreal KV
```python
from surrealdb import SurrealDB

db = SurrealDB("surrealkv://path/to/dbfile.kv")
```
For Memory
```python
from surrealdb import SurrealDB

db = SurrealDB("mem://")
db = SurrealDB("memory://")
```

## Additional Examples
### Insert and Retrieve Data
```python
from surrealdb import SurrealDB

db = SurrealDB("ws://localhost:8000")
db.connect()
db.use("example_ns", "example_db")
db.sign_in("root", "root")

# Insert a record
new_user = {"name": "Alice", "age": 30}
inserted_record = db.insert("users", new_user)
print(f"Inserted Record: {inserted_record}")

# Retrieve the record
retrieved_users = db.select("users")
print(f"Retrieved Users: {retrieved_users}")

db.close()
```

### Perform a Custom Query
```python
from surrealdb import AsyncSurrealDB

async def main():
    async with AsyncSurrealDB(url="ws://localhost:8000") as db:
        await db.sign_in("root", "root")
        await db.use("test", "test")

        query = "SELECT * FROM users WHERE age > min_age;"
        variables = {"min_age": 25}

        results = await db.query(query, variables)
        print(f"Query Results: {results}")

asyncio.run(main())
```

### Manage Authentication
```python
from surrealdb import SurrealDB

with SurrealDB(url="ws://localhost:8080") as db:
    # Sign up a new user
    token = db.sign_up(username="new_user", password="secure_password")
    print(f"New User Token: {token}")
    
    # Sign in as an existing user
    token = db.sign_in(username="existing_user", password="secure_password")
    print(f"Signed In Token: {token}")
    
    # Authenticate using a token
    db.authenticate(token=token)
    print("Authentication successful!")
```

### Live Query Notifications
```python
import asyncio
from surrealdb.surrealdb import SurrealDB

db = SurrealDB("ws://localhost:8080")
db.connect()
db.use("example_ns", "example_db")

# Start a live query
live_id = db.live("users")

# Process live notifications
notifications = db.live_notifications(live_id)

async def handle_notifications():
    while True:
        notification = await notifications.get()
        print(f"Live Notification: {notification}")

# Run the notification handler
asyncio.run(handle_notifications())
```

### Upserting Records
```python
from surrealdb.surrealdb import SurrealDB

with SurrealDB("ws://localhost:8000") as db:
    db.sign_in("root", "root")
    db.use("example_ns", "example_db")

    upsert_data = { "name": "Charlie", "age": 35}
    result = db.upsert("users", upsert_data)
    print(f"Upsert Result: {result}")
```

## Contributing
Contributions to this library are welcome! If you encounter issues, have feature requests, or 
want to make improvements, feel free to open issues or submit pull requests.

