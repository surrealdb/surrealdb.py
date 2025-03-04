<br>

<p align="center">
	<img width=120 src="https://raw.githubusercontent.com/surrealdb/icons/main/surreal.svg" />
	&nbsp;
	<img width=120 src="https://raw.githubusercontent.com/surrealdb/icons/main/python.svg" />
</p>

<h3 align="center">The official SurrealDB SDK for Python.</h3>

<br>

<p align="center">
	<a href="https://github.com/surrealdb/surrealdb.py"><img src="https://img.shields.io/badge/status-stable-ff00bb.svg?style=flat-square"></a>
	&nbsp;
	<a href="https://surrealdb.com/docs/integration/libraries/python"><img src="https://img.shields.io/badge/docs-view-44cc11.svg?style=flat-square"></a>
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

The official SurrealDB SDK for Python. If you find that the python SDK is not behaving exactly how you expect, please check the gottas section at the bottom of this README to see if your problem can be quickly solved. 

## Documentation

View the SDK documentation [here](https://surrealdb.com/docs/integration/libraries/python).

## How to install

```sh
pip install surrealdb
```

# Quick start

In this short guide, you will learn how to install, import, and initialize the SDK, as well as perform the basic data manipulation queries. 
This guide uses the `Surreal` class, but this example would also work with `AsyncSurreal` class, with the addition of `await` in front of the class methods.


## Install

```sh
pip install surrealdb
```

## Learn the basics

```python

# Import the Surreal class
from surrealdb import Surreal

# Using a context manger to automatically connect and disconnect
with Surreal("ws://localhost:8000/rpc") as db:
    db.signin({"username": 'root', "password": 'root'})
    db.use("namepace_test", "database_test")

    # Create a record in the person table
    db.create(
        "person",
        {
            "user": "me",
            "password": "safe",
            "marketing": True,
            "tags": ["python", "documentation"],
        },
    )

    # Read all the records in the table
    print(db.select("person"))

    # Update all records in the table
    print(db.update("person", {
        "user":"you",
        "password":"very_safe",
        "marketing": False,
        "tags": ["Awesome"]
    }))

    # Delete all records in the table
    print(db.delete("person"))

    # You can also use the query method 
    # doing all of the above and more in SurrealQl
    
    # In SurrealQL you can do a direct insert 
    # and the table will be created if it doesn't exist
    
    # Create
    db.query("""
    insert into person {
        user: 'me',
        password: 'very_safe',
        tags: ['python', 'documentation']
    };
    """)

    # Read
    print(db.query("select * from person"))
    
    # Update
    print(db.query("""
    update person content {
        user: 'you',
        password: 'more_safe',
        tags: ['awesome']
    };
    """))

    # Delete
    print(db.query("delete person"))
```

## Next steps

Now that you have learned the basics of the SurrealDB SDK for Python, you can learn more about the SDK and its methods [in the methods section](https://surrealdb.com/docs/sdk/python/methods) and [data types section](https://surrealdb.com/docs/sdk/python/data-types).

## Contributing

Contributions to this library are welcome! If you encounter issues, have feature requests, or 
want to make improvements, feel free to open issues or submit pull requests.

If you want to contribute to the Github repo please read the general contributing guidelines on concepts such as how to create a pull requests [here](https://github.com/surrealdb/surrealdb.py/blob/main/CONTRIBUTING.md).

## Getting the repo up and running

To contribute, it's a good idea to get the repo up and running first. We can do this by running the tests. If the tests pass, your `PYTHONPATH` works and the client is making successful calls to the database. To do this we must run the database with the following command:

```bash
# if the docker-compose binary is installed
docker-compose up -d

# if you are running docker compose directly through docker
docker compose up -d
```

Now that the database is running, we can enter a terminal session with all the requirements installed and `PYTHONPATH` configured with the command below:

```bash
bash scripts/term.sh
```

You will now be running an interactive terminal through a python virtual environment with all the dependencies installed. We can now run the tests with the following command:

```bash
python -m unittest discover
```

The number of tests might increase but at the time of writing this you should get a printout like the one below:

```bash
.........................................................................................................................................Error in live subscription: sent 1000 (OK); no close frame received
..........................................................................................
----------------------------------------------------------------------
Ran 227 tests in 6.313s

OK
```
Finally, we clean up the database with the command below:
```bash
# if the docker-compose binary is installed
docker-compose down

# if you are running docker compose directly through docker
docker compose down
```
To exit the terminal session merely execute the following command:
```bash
exit
```
 And there we have it, our tests are passing.

## Gottas

Due to quirks either unearthed by python or how the `cbor` serialization library handles data, there are some slight quirks that you might not expect. This section clarifies these quirks, why they exist, and how to handle them.

### None types

Python's `cbor` library serializes `None` types automatically before they have a chance of reaching our encoder. While we are looking into ways to override default serialization methods, we have our own data type that denotes a `None` type which can be shown below:

```python
from surrealdb import AsyncSurreal, NoneType, RecordID

vars = {
    "username": "root",
    "password": "root"
}

schema = """
    DEFINE TABLE person SCHEMAFULL TYPE NORMAL;
    DEFINE FIELD name ON person TYPE string;
    DEFINE FIELD age ON person TYPE option<int>;
"""
connection = AsyncSurreal("ws://localhost:8000/rpc")
await connection.query(schema)

outcome = await connection.create(
    "person:john",
    {"name": "John", "age": None}
)
record_check = RecordID(table_name="person", identifier="john")
self.assertEqual(record_check, outcome["id"])
self.assertEqual("John", outcome["name"])
# below we need a .get because fields with None are currently not serialized
# a .get gives the same result
self.assertEqual(None, outcome.get("age"))
```

It must be noted that the field that had a `None` is not returned as a field at all. Using a `.get()` function will give the same effect as if the field is there but it is a `None`. Using a `outcome["age"]` will throw an error. We can also see how it works when the field is not None with the following code:

```python
outcome = await connection.create(
    "person:dave",
    {"name": "Dave", "age": 34}
)
record_check = RecordID(table_name="person", identifier="dave")
self.assertEqual(record_check, outcome["id"])
self.assertEqual("Dave", outcome["name"])
self.assertEqual(34, outcome["age"])
```
Here we can see that the age is returned because it is not `None`. There is a slight performance cost for this `None` safety as the client needs to recursively go through the data passed into the client replacing `None` with `NoneType`. If you do not want this performance cost, you can disable the check but you have to ensure that all `None` types you pass into the client are replaced yourself. You can us a `NoneType` via the following code:

```python
from surrealdb import AsyncSurreal, NoneType, RecordID
import os

vars = {
    "username": "root",
    "password": "root"
}

schema = """
    DEFINE TABLE person SCHEMAFULL TYPE NORMAL;
    DEFINE FIELD name ON person TYPE string;
    DEFINE FIELD age ON person TYPE option<int>;
"""
connection = AsyncSurreal("ws://localhost:8000/rpc")
await connection.query(schema)

# bypass the recursive check to replace None with NoneType
os.environ["SURREALDB_BYPASS_CHECKS"] = "true"

outcome = await connection.create(
    "person:john",
    {"name": "John", "age": None}
)
record_check = RecordID(table_name="person", identifier="john")
self.assertEqual(record_check, outcome["id"])
self.assertEqual("John", outcome["name"])
# below we need a .get because fields with None are currently not serialized
# a .get gives the same result
self.assertEqual(None, outcome.get("age"))
```

Here we set the environment variable `SURREALDB_BYPASS_CHECKS` to `"true"`. 
