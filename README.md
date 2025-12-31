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

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and [hatch](https://hatch.pypa.io/) as the build tool.

### Prerequisites

Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Dependency Philosophy

This project follows library best practices for dependency management:
- **Minimal constraints**: Uses `>=` instead of exact pins for maximum compatibility
- **Essential only**: Only direct dependencies that are actually imported
- **Clean separation**: Development tools in separate dependency groups
- **Well-maintained tools**: Avoid dependencies which go 6+ months without so much as a patch

### Development Workflow

1. **Install dependencies:**
   ```bash
   # Install main dependencies
   uv sync
   
   # Install with dev dependencies (linting, type checking, testing)
   uv sync --group dev
   ```

2. **Run development tools:**
   ```bash
   # Run linting
   uv run ruff check src/
   
   # Run formatting
   uv run ruff format src/
   
   # Run type checking
   uv run mypy --explicit-package-bases src/
   
   # Run tests (with coverage)
   uv run scripts/run_tests.sh
   # Or directly:
   uv run pytest --cov=src/surrealdb --cov-report=term-missing --cov-report=html
   ```

3. **Build the project:**
   ```bash
   uv build
   ```

## Testing Strategy

We use a multi-tier testing strategy to ensure compatibility across SurrealDB versions:

### Local Development Testing

```bash
# Test with default version (latest stable)
docker-compose up -d
uv run scripts/run_tests.sh

# Test against specific version
./scripts/test-versions.sh v2.1.8

# Test against different v2.x versions
SURREALDB_VERSION=v2.0.5 uv run scripts/run_tests.sh
SURREALDB_VERSION=v2.3.6 uv run scripts/run_tests.sh
```

### CI/CD Testing

- **Core Tests**: Run on every PR against key stable versions (v2.0.5, v2.1.8, v2.2.6, v2.3.6)
- **Comprehensive Tests**: Run on schedule/manual trigger against all latest minor versions  
- **Python Compatibility**: Tests all supported Python versions (3.10, 3.11, 3.12, 3.13)

### Version-Specific Behavior

Tests are designed to be version-agnostic across all supported SurrealDB v2.x versions:
- Automatically handles behavioral differences between v2.x minor versions
- No environment variable configuration required for version detection

## Documentation

View the SDK documentation [here](https://surrealdb.com/docs/integration/libraries/python).

## How to install

```sh
# Using pip
pip install surrealdb

# Using uv
uv add surrealdb
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

## Embedded Database

SurrealDB can also run embedded directly within your Python application natively. This provides a fully-featured database without needing a separate server process.

### Installation

The embedded database is included when you install surrealdb:

```sh
pip install surrealdb
```

For source builds, you'll need Rust toolchain and maturin:

```sh
uv run maturin develop --release
```

### In-Memory Database

Perfect for embedded applications, development, testing, caching, or temporary data.

```python
import asyncio
from surrealdb import AsyncSurreal

async def main():
    # Create an in-memory database (can use "mem://" or "memory")
    async with AsyncSurreal("memory") as db:
        await db.use("test", "test")
        await db.signin({"username": "root", "password": "root"})
        
        # Use like any other SurrealDB connection
        person = await db.create("person", {
            "name": "John Doe",
            "age": 30
        })
        print(person)
        
        people = await db.select("person")
        print(people)

asyncio.run(main())
```

### File-Based Persistent Database

For persistent local storage:

```python
import asyncio
from surrealdb import AsyncSurreal

async def main():
    # Create a file-based database (can use "file://" or "surrealkv://")
    async with AsyncSurreal("file://mydb") as db:
        await db.use("test", "test")
        await db.signin({"username": "root", "password": "root"})
        
        # Data persists across connections
        await db.create("company", {
            "name": "Acme Corp",
            "employees": 100
        })
        
        companies = await db.select("company")
        print(companies)

asyncio.run(main())
```

### Blocking (Sync) API

The embedded database also supports the blocking API:

```python
from surrealdb import Surreal

# In-memory (can use "mem://" or "memory")
with Surreal("memory") as db:
    db.use("test", "test")
    db.signin({"username": "root", "password": "root"})
    
    person = db.create("person", {"name": "Jane"})
    print(person)

# File-based
with Surreal("file://mydb") as db:
    db.use("test", "test")
    db.signin({"username": "root", "password": "root"})
    
    company = db.create("company", {"name": "TechStart"})
    print(company)
```

### When to Use Embedded vs Remote

**Use Embedded (`memory`, `mem://`, `file://`, or `surrealkv://`) when:**
- Building desktop applications
- Running tests (in-memory is very fast)
- Local development without server setup
- Embedded systems or edge computing
- Single-application data storage

**Use Remote (`ws://` or `http://`) when:**
- Multiple applications share data
- Distributed systems
- Cloud deployments
- Need horizontal scaling
- Centralized data management

For more examples, see the [`examples/embedded/`](examples/embedded/) directory.

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
pytest --cov=src/surrealdb --cov-report=term-missing --cov-report=html
```

The number of tests might increase but at the time of writing this you should get a printout like the one below:

```bash
================================ test session starts ================================
platform ...
collected 227 items

....................................................................................
... (test output)

---------- coverage: platform ... -----------
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
src/surrealdb/....
...

============================= 227 passed in 6.31s ================================
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

## Testing Against Different SurrealDB Versions

### Quick Testing with Docker Compose

Test against different SurrealDB versions using environment variables:

```bash
# Test with latest v2.x (default: v2.3.6)
uv run scripts/run_tests.sh

# Test with specific v2.x version  
SURREALDB_VERSION=v2.1.8 docker-compose up -d surrealdb
uv run scripts/run_tests.sh

# Use different profiles for testing specific v2.x versions
docker-compose --profile v2-0 up -d    # v2.0.5 on port 8020
docker-compose --profile v2-1 up -d    # v2.1.8 on port 8021
docker-compose --profile v2-2 up -d    # v2.2.6 on port 8022
docker-compose --profile v2-3 up -d    # v2.3.6 on port 8023
```

### Automated Version Testing

Use the test script for systematic testing:

```bash
# Test latest version with all tests
./scripts/test-versions.sh

# Test specific version
./scripts/test-versions.sh v2.1.8

# Test specific test directory
./scripts/test-versions.sh v2.3.6 tests/unit_tests/data_types
```

### GitHub Actions Matrix Testing

The CI automatically tests against multiple versions:

- **Core tests**: Always run against key versions (v2.0.5, v2.1.8, v2.2.6, v2.3.6)
- **Comprehensive tests**: Scheduled tests against all latest versions
- **Auto-discovery**: Dynamically finds latest patch versions

## Docker Usage

### Using the Official Docker Image

```bash
# Build the image
docker build -t surrealdb-python:latest .

# Run with uv
docker run -it surrealdb-python:latest uv run python -c "import surrealdb; print('Ready!')"

# Run tests in container
docker run -it surrealdb-python:latest uv run python -m unittest discover -s tests
```

### Development with Docker Compose

```bash
# Start latest SurrealDB for development
docker-compose up -d

# Start specific version for testing
SURREALDB_VERSION=v2.1.8 docker-compose up -d

# View logs
docker-compose logs -f surrealdb
```

# SurrealDB Python SDK

[![Tests](https://github.com/surrealdb/surrealdb.py/workflows/Tests/badge.svg)](https://github.com/surrealdb/surrealdb.py/actions)
[![PyPI version](https://badge.fury.io/py/surrealdb.svg)](https://badge.fury.io/py/surrealdb)
[![Python](https://img.shields.io/pypi/pyversions/surrealdb.svg)](https://pypi.org/project/surrealdb/)

The official SurrealDB Python SDK.

## Requirements

- **Python**: 3.9 or greater
- **SurrealDB**: v2.0.0 to v2.3.6 (for remote connections)
- **Rust toolchain**: Only required if building from source

> **Note**: This SDK works seamlessly with SurrealDB versions v2.0.0 to v2.3.6, ensuring compatibility with the latest features. The embedded database functionality is included in pre-built wheels on PyPI.

## Quick Start

1. **Install the SDK**:
   ```bash
   # Using pip
   pip install surrealdb
   ```

   ```bash
   # Using uv
   uv add surrealdb
   ```

2. **Start SurrealDB** (using Docker):
   ```bash
   docker run --rm -p 8000:8000 surrealdb/surrealdb:v2.3.6 start --allow-all
   ```

3. **Connect and query**:
   ```python
   from surrealdb import Surreal

   async def main():
       async with Surreal("ws://localhost:8000/rpc") as db:
           await db.signin({"user": "root", "pass": "root"})
           await db.use("test", "test")
           
           # Create
           person = await db.create("person", {"name": "John", "age": 30})
           print(person)
           
           # Query
           people = await db.select("person")
           print(people)

   import asyncio
   asyncio.run(main())
   ```

## Development

This project uses **uv** for fast dependency management and **maturin** for building.

### Setup

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup**:
   ```bash
   git clone https://github.com/surrealdb/surrealdb.py.git
   cd surrealdb.py
   uv sync --group dev
   ```

3. **Activate environment**:
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

### Testing

#### Quick Test (Latest Version)
```bash
# Start SurrealDB v2.3.6
docker compose up -d

# Run tests
export SURREALDB_URL="http://localhost:8000"
uv run python -m unittest discover -s tests
```

#### Test Multiple Versions
```bash
# Test latest v2.x versions
./scripts/test-versions.sh --v2-latest

# Test specific version
./scripts/test-versions.sh v2.1.8

# Test all supported versions
./scripts/test-versions.sh --all
```

#### Available Docker Profiles
```bash
# Development (default - v2.3.6)
docker compose up -d

# Test specific v2.x versions
docker compose --profile v2-0 up -d    # v2.0.5 on port 8020
docker compose --profile v2-1 up -d    # v2.1.8 on port 8021  
docker compose --profile v2-2 up -d    # v2.2.6 on port 8022
docker compose --profile v2-3 up -d    # v2.3.6 on port 8023
```

### Code Quality

```bash
# Format code
uv run ruff format

# Lint code  
uv run ruff check

# Type checking
uv run mypy src/
uv run pyright src/
```

TODO: migrate to basedpyright. Try it with `uvx run basedpyright src/`

### Release

```bash
# Build package
uv build

# Publish to PyPI (requires authentication)
uv publish
```

## SurrealDB Version Support

This Python SDK supports **SurrealDB v2.0.0 to v2.3.6**. Here's the compatibility matrix:

| Python SDK | SurrealDB Versions | Status |
|------------|-------------------|---------|
| v1.0.0+    | v2.0.0 - v2.3.6   | ✅ Supported |
| v1.0.0+    | v1.x.x            | ❌ Not supported |

### Tested Versions

The SDK is continuously tested against:
- **v2.0.5** (Latest v2.0.x)
- **v2.1.8** (Latest v2.1.x) 
- **v2.2.6** (Latest v2.2.x)
- **v2.3.6** (Latest v2.3.x)

## Documentation

- [Official Documentation](https://surrealdb.com/docs/sdk/python)
- [API Reference](https://docs.rs/surrealdb)
- [Examples](./examples)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

# Running Tests and Coverage

To run all tests with coverage reporting:

```bash
uv run pytest --cov=src/surrealdb --cov-report=term-missing --cov-report=html
```

This will:
- Run all tests using pytest
- Show a coverage summary in the terminal
- Generate an HTML coverage report in the `htmlcov/` directory

To test a specific file:

```bash
uv run pytest tests/unit_tests/connections/test_connection_constructor.py --cov=src/surrealdb
```

To view the HTML coverage report, open `htmlcov/index.html` in your browser after running the tests.
