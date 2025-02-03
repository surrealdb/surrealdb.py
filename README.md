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

The official SurrealDB SDK for Python.

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

