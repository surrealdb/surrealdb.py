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

# Documentation

View the SDK documentation [here](https://surrealdb.com/docs/integration/libraries/python).

# How to install

```sh
pip install surrealdb
```

# Basic Usage
> All examples assume SurrealDB is [installed](https://surrealdb.com/install) and running on port 8000.
## Initialization
To start using the database, create an instance of SurrealDB, connect to your SurrealDB server, and specify the
namespace and database you wish to work with.
```
from surrealdb.surrealdb import SurrealDB

# Connect to the database
db = SurrealDB(url="ws://localhost:8080")
db.connect()
db.use("namespace", "database_name")
```

## Using context manager
The library supports Python’s context manager to manage connections automatically. 
This ensures that connections are properly closed when the block of code finishes executing.
```
from surrealdb.surrealdb import SurrealDB

with SurrealDB(url="ws://localhost:8080") as db:
    db.use("namespace", "database_name")
```
# Meta Information
## info() -> dict
Retrieve information about the current authenticated user.

## version() -> str
Retrieve the server version.

# Connection Management
## connect()
Establishes a connection to the SurrealDB server. This method should be called before performing 
any database operations. It is automatically called when using a context manager. An exception is raised if 
connection fails

## close()
Close the active database connection. If using a context manager, this will be handled automatically.

## use(namespace: str, database: str)
Specify the namespace and database to use for subsequent operations. Both parameters are required.

## Authentication
### sign_in(username: str, password: str) -> str
Log in to the database with a username and password. Returns a JWT token upon successful authentication. The token
is stored as part of the initialized db instance

### sign_up(username: str, password: str) -> str
Register a new user with the given username and password. Returns a JWT token for the newly created user. The token
is stored as part of the initialized db instance

### authenticate(token: str)
Authenticates a JWT token. Raises an exception otherwise. If valid, the token is stored as part of the initialized db instance

### invalidate(token: str)
Invalidate a previously issued JWT token to terminate a session.


## Data Manipulation
### create(thing, data)
Create a new record in a table or with a specified ID. `thing` is a table or record id
If only a table is provided, a random ID will be generated. 

### select(thing)
Retrieve data from a table or record. `thing` is a table or record id

### update(thing, data)
Replace an entire record or all records in a table with new data. `thing` is a table or record id

### delete(thing)
Remove a specific record or all records from a table. `thing` is a table or record id

### merge(thing, data)
Merge new data into an existing record or records. `thing` is a table or record id

### upsert(thing, data)
Insert a new record or update an existing one, ensuring no duplicate entries. `thing` is a table or record id

## Query Execution
### set(name, value)

### unset(name)

### query(query: str, variables: dict = {}) -> List[dict]
Execute a custom SurrealQL query with optional variables for dynamic content. Variable set via the `set` method are available to be the query sql.
The results are returned as a list of dictionaries.

## Live Queries
Live queries enable monitoring of real-time changes in the database. This is particularly useful for applications requiring immediate 
updates when data changes.

### live(thing, diff: bool = False) -> uuid.UUID
Initiate a live query on a table. If diff is set to True, the live notifications will contain JSON Patches instead of full record data.

### kill(live_query_id: uuid.UUID)
Terminate an active live query.

### live_notifications(live_id: uuid.UUID) -> asyncio.Queue
Receive notifications for live query changes.


## Usage Examples
### Insert and Retrieve Data
```python
db = SurrealDB("ws://localhost:8080")
db.connect()
db.use("example_ns", "example_db")

# Insert a record
new_user = {"name": "Alice", "age": 30}
inserted_record = db.insert("users", new_user)
print(f"Inserted Record: {inserted_record}")

# Retrieve the record
retrieved_users = db.select("users")
print(f"Retrieved Users: {retrieved_users}")
```

### Perform a Custom Query
```python
query = "SELECT * FROM users WHERE age > $min_age"
variables = {"min_age": 25}

results = db.query(query, variables)
print(f"Query Results: {results}")
```

### Manage Authentication
```python
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
``` python
upsert_data = {"id": "user:123", "name": "Charlie", "age": 35}
result = db.upsert("users", upsert_data)
print(f"Upsert Result: {result}")
```

## Contributing
Contributions to this library are welcome! If you encounter issues, have feature requests, or 
want to make improvements, feel free to open issues or submit pull requests.

