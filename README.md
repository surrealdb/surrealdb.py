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
    <a href="https://x.com/surrealdb"><img src="https://img.shields.io/badge/x-follow_us-222222.svg?style=flat-square" alt="X"></a>
    &nbsp;
    <a href="https://www.linkedin.com/company/surrealdb/"><img src="https://img.shields.io/badge/linkedin-connect_with_us-0a66c2.svg?style=flat-square"></a>
    &nbsp;
    <a href="https://www.youtube.com/channel/UCjf2teVEuYVvvVC-gFZNq6w"><img src="https://img.shields.io/badge/youtube-subscribe-fc1c1c.svg?style=flat-square"></a>
</p>

# surrealdb.py

The official SurrealDB SDK for Python.

## Documentation

View the SDK documentation [here](https://surrealdb.com/docs/sdk/python).

## How to install

```sh
# Using pip
pip install surrealdb

# Using uv
uv add surrealdb
```

## Quick start

In this short guide, you will learn how to install, import, and initialize the SDK, as well as perform the basic data manipulation queries. 

This guide uses the `Surreal` class, but this example would also work with `AsyncSurreal` class, with the addition of `await` in front of the class methods.

## Running SurrealDB

You can run SurrealDB locally or start with
a [free SurrealDB cloud account](https://surrealdb.com/docs/cloud/getting-started).

For local, two options:

1. [Install SurrealDB](https://surrealdb.com/docs/surrealdb/installation)
  and [run SurrealDB](https://surrealdb.com/docs/surrealdb/installation/running). Run in-memory with:

  ```bash
  surreal start -u root -p root
  ```

2. [Run with Docker](https://surrealdb.com/docs/surrealdb/installation/running/docker).

  ```bash
  docker run --rm --pull always -p 8000:8000 surrealdb/surrealdb:latest start
  ```

## Learn the basics

```python

# Import the Surreal class
from surrealdb import Surreal, RecordID, Table

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

## CRUD builder pattern (v3.0)

`create`, `update`, `upsert`, `delete`, and `insert` return an awaitable
(or lazy, for sync) builder. The builder exposes chainable clause methods
that map directly to SurrealQL clauses.

```python
from surrealdb import AsyncSurreal, RecordID, Table

async with AsyncSurreal("ws://localhost:8000/rpc") as db:
    await db.signin({"username": "root", "password": "root"})
    await db.use("ns", "db")

    # Sugar: db.create(record, data) is equivalent to .content(data)
    await db.create(RecordID("person", "tobie"), {"name": "Tobie"})

    # Or use the builder explicitly
    await db.create(RecordID("person", "tobie")).content({"name": "Tobie"})
    await db.update(RecordID("person", "tobie")).replace({"name": "Tobie"})
    await db.update(RecordID("person", "tobie")).merge({"vip": True})
    await db.update(RecordID("person", "tobie")).patch([
        {"op": "replace", "path": "/vip", "value": False},
    ])

    # `insert` accepts a `relation=True` kwarg or a chained `.relation()`
    await db.insert(Table("likes"), {"in": ..., "out": ...}, relation=True)
    await db.insert(Table("likes")).relation().content({"in": ..., "out": ...})
```

The builder is **typed** via `@overload`:

- `RecordID` target -> `dict[str, Value]`
- `Table` target   -> `list[Value]`
- `str` target     -> `Value` (a record-id string returns a dict; a table-name
  string returns a list - the type checker can't tell them apart, so falls back to `Value`)

Sync usage is similar, but the clause methods are **terminal** (there is
no `await` to defer to, so they run immediately and return the result):

```python
from surrealdb import Surreal

with Surreal("ws://localhost:8000/rpc") as db:
    db.signin({"username": "root", "password": "root"})
    db.use("ns", "db")

    # Terminal: .merge runs the UPDATE and returns the result dict.
    out = db.create(RecordID("person", "tobie")).merge({"name": "Tobie"})

    # No-clause form: lazy builder; auto-executes the first time you
    # consume it (indexing, iteration, ==, attribute access, ...).
    builder = db.create(RecordID("person", "alice"))
    print(builder["id"])  # <- triggers execution, returns the dict's "id"

    # Fire-and-forget: call .execute() because no consumption happens.
    db.query("DELETE temp_data;").execute()
```

> Note: `__repr__` and `__str__` on a pending sync builder return a
> `"<...pending>"` placeholder rather than executing the operation, so
> debuggers, loggers, and `print()` cannot accidentally fire pending
> queries or mutations.
>
> ⚠ **Truthiness and comparison** auto-execute though.
> `if db.query("DELETE foo;")`, `bool(db.create(...))`, and
> `db.create(...) == something` will all run the operation. If you want
> fire-and-forget, call `.execute()` explicitly. The full list of
> auto-executing magic methods is `__getitem__`, `__iter__`, `__len__`,
> `__contains__`, `__eq__`, `__ne__`, `__bool__`, and `__getattr__`.

### Thread safety

Sync builders guard their cache with a per-builder lock so consuming the
same builder from multiple threads issues exactly one RPC. They are
**not** safe for concurrent *reconfiguration* though — calling `.merge()`
on one thread while another consumes the result is a race on the
builder's clause/data state that the lock does not cover. Treat builders
as single-shot, single-owner values; pass the realised result between
threads, not the builder itself.

The underlying `BlockingWsSurrealConnection` is itself thread-safe (it
serialises send/recv with an internal lock), so sharing a connection
across threads and creating per-thread builders against it is fine.

### Async cancellation and server truth

If you `cancel()` an async task that's awaiting an in-flight builder,
the SDK does the right thing on the *client* side: the cache is reset so
fresh callers retry, and concurrent peer awaiters see a `SurrealError`
rather than a phantom `CancelledError` they didn't request.

What it cannot do is roll back the *server*. Once an RPC has reached
SurrealDB, the operation may still complete server-side even after the
client cancels. For mutations this means cancellation is **not** an
abort — re-read the affected records before assuming "nothing happened",
or wrap mutations in a `BEGIN ... COMMIT` block via `query()` if you
need atomic rollback semantics.

## Multi-statement queries and transactions (issue #232 fix)

`query()` now surfaces every statement result. When the server returns a
single result, `query()` returns a single Value. When it returns multiple
(multi-statement queries or `BEGIN ... COMMIT` blocks), `query()` returns
a `tuple[Value, ...]`.

```python
single = await db.query("SELECT * FROM person")
many = await db.query(
    "SELECT * FROM person; SELECT count() FROM person GROUP ALL"
)
# many is (people_list, count_list)
```

You can also map the N statement results onto a dataclass via `.into()`:

```python
from dataclasses import dataclass

@dataclass
class Stats:
    created: dict
    all_people: list
    count: int

result = await db.query(
    "CREATE person:tobie SET name = 'Tobie';"
    "SELECT * FROM person;"
    "SELECT count() FROM person GROUP ALL"
).into(Stats)
```

For the raw server response (status, time, error per statement), keep
using `query_raw()`.

## Client-side transactions and sessions

Multi-session and client-side transactions are supported **only for
WebSocket connections** (`ws://` or `wss://`). They are not available for
HTTP or embedded connections.

```python
async with AsyncSurreal("ws://localhost:8000/rpc") as db:
    await db.signin({"username": "root", "password": "root"})
    await db.use("ns", "db")

    # Create a session
    session = await db.new_session()
    await session.use("ns", "db")

    # Start a transaction on the session
    txn = await session.begin_transaction()
    await txn.create(RecordID("account", "alice"), {"balance": 100})
    await txn.update(RecordID("account", "bob")).merge({"balance": 50})

    # Commit (or call `await txn.cancel()` to roll back)
    await txn.commit()

    await session.close_session()
```

The same CRUD builder, query, and `run()` API is available on both
`AsyncSurrealSession` / `BlockingSurrealSession` and
`AsyncSurrealTransaction` / `BlockingSurrealTransaction`.

## `run()` - calling SurrealDB functions

```python
result = await db.run("fn::increment", [1])
greeting = await db.run("fn::greet", ["world"])
```

## Live queries

Live queries let you subscribe to changes on a table and receive a
notification whenever a record is created, updated, or deleted. They are a
**WebSocket-only** feature (`ws://` or `wss://`).

The API is three methods:

- `live(table, diff=False)` - start a live query on a table and return its
  `UUID`. Pass `diff=True` to receive JSON Patch diffs instead of full
  records.
- `subscribe_live(query_uuid)` - return a generator (async generator for the
  async client) that yields notification dicts. Each notification has an
  `"action"` (`"CREATE"`, `"UPDATE"`, or `"DELETE"`) and a `"result"` (the
  affected record).
- `kill(query_uuid)` - stop a running live query.

You can also start a live query through `query("LIVE SELECT * FROM ...")`,
which returns the same `UUID` you can pass to `subscribe_live()`.

### Async

```python
import asyncio
from surrealdb import AsyncSurreal

async def main():
    # Connection that owns the subscription.
    async with AsyncSurreal("ws://localhost:8000/rpc") as db:
        await db.signin({"username": "root", "password": "root"})
        await db.use("ns", "db")

        live_id = await db.live("person")           # -> UUID
        subscription = await db.subscribe_live(live_id)

        # Drive the mutation on a SEPARATE connection (see caveats below).
        async with AsyncSurreal("ws://localhost:8000/rpc") as writer:
            await writer.signin({"username": "root", "password": "root"})
            await writer.use("ns", "db")
            await writer.create("person", {"name": "Jaime"})

        # Wait for the notification (guard with a timeout in real code).
        notification = await asyncio.wait_for(subscription.__anext__(), timeout=10)
        print(notification["action"])   # "CREATE"
        print(notification["result"])   # the created record

        await db.kill(live_id)

asyncio.run(main())
```

### Blocking

```python
from surrealdb import Surreal

with Surreal("ws://localhost:8000/rpc") as db:
    db.signin({"username": "root", "password": "root"})
    db.use("ns", "db")

    live_id = db.live("person")            # -> UUID
    subscription = db.subscribe_live(live_id)

    # Mutate on a SEPARATE connection so the notification can arrive.
    with Surreal("ws://localhost:8000/rpc") as writer:
        writer.signin({"username": "root", "password": "root"})
        writer.use("ns", "db")
        writer.create("person", {"name": "Jaime"})

    for notification in subscription:
        print(notification["action"], notification["result"])
        break                              # generator blocks for the next one

    db.kill(live_id)
```

### Caveats

- **Mutate on a separate connection.** The connection that owns a
  subscription is busy receiving live notifications, so running
  `CREATE`/`UPDATE`/`DELETE` on that *same* connection races the query
  responses against the incoming notifications. Perform the mutations that
  should trigger notifications on a **second** connection (this is exactly
  what the test suite does).
- **Blocking client: one subscriber per connection.** The blocking
  `subscribe_live()` reads notifications straight off the socket, so a single
  blocking connection supports only **one** concurrent subscriber. Use a
  separate connection per live subscription (or the async client, which
  fans notifications out to per-subscriber queues).

## Migrating from 2.x

v3.0 is a breaking change. Highlights:

| 2.x                                              | 3.0                                                       |
| ------------------------------------------------ | --------------------------------------------------------- |
| `db.merge(record, data)`                         | `db.update(record).merge(data)`                           |
| `db.patch(record, data)`                         | `db.update(record).patch(data)`                           |
| `db.insert_relation(table, data)`                | `db.insert(table, data, relation=True)`                   |
| `db.query("SELECT 1; SELECT 2")` -> first result | `db.query("SELECT 1; SELECT 2")` -> `tuple` of all results |
| n/a                                              | `db.run("fn::name", [args])`                              |
| n/a                                              | `db.query("...").into(MyDataclass)`                       |
| Sync `db.query("DELETE foo")` runs immediately   | Sync `db.query("DELETE foo").execute()` (lazy builder)     |
| `db.delete("my-table")` (silently inlined)       | `db.delete(Table("my-table"))` (raw string rejected)      |

> Bare-string resource targets are now strictly validated against the
> safe-identifier pattern (`[A-Za-z_][A-Za-z0-9_]*`) so user-supplied
> strings can never be concatenated into the generated SurrealQL. Names
> with hyphens, spaces, or other special characters must be wrapped in
> `Table(...)` or `RecordID(...)`, both of which are parameter-bound.

## Embedded Database

SurrealDB can also run embedded directly within your Python application natively. This provides a fully-featured database without needing a separate server process.

### Installation

The embedded database is included when you install `surrealdb`.

Install the SDK using `pip`:

```bash
pip install surrealdb
```

Or install using `uv`:

```bash
uv add surrealdb
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

## Sessions in detail

- **Sessions**: Call `attach()` on a WS connection to create a new session (returns a `UUID`). Use `new_session()` to get an `AsyncSurrealSession` or `BlockingSurrealSession` that scopes all operations to that session. Call `close_session()` on the session (or `detach(session_id)` on the connection) to drop it.
- **Transactions**: On a session (or the default connection - though typical practice is to start on a session), call `begin_transaction()` to obtain a `Transaction` whose builder calls all participate in the same transaction. Call `commit()` to apply, or `cancel()` to roll back.

On HTTP or embedded connections, `attach()`, `detach()`, `begin()`, `commit()`, `cancel()`, and `new_session()` raise `UnsupportedFeatureError` with a message that sessions/transactions are only supported for WebSocket connections.

## Observability with Logfire

[Pydantic Logfire](https://docs.pydantic.dev/logfire/) provides automatic instrumentation for SurrealDB operations, giving you instant observability into your database interactions. Logfire exports standard OpenTelemetry spans, making it compatible with any observability platform.

### Quick start

Install Logfire using `pip`:

```bash
pip install logfire
```

Or install using `uv`:

```bash
uv add logfire
```

**Usage**:

```python
import logfire
from surrealdb import AsyncSurreal

# Configure Logfire
logfire.configure()

# Instrument all SurrealDB operations
logfire.instrument_surrealdb()

# All database operations are now automatically traced
async with AsyncSurreal("ws://localhost:8000") as db:
    await db.signin({"username": "root", "password": "root"})
    await db.use("test", "test")
    
    # These operations will appear as spans in your traces
    await db.create("person", {"name": "Alice"})
    await db.query("SELECT * FROM person")
```

### Features

- **Automatic tracing**: All database methods are instrumented automatically
- **Smart parameter logging**: Sensitive data (tokens, passwords) are automatically scrubbed
- **OpenTelemetry compatible**: Works with Jaeger, DataDog, Honeycomb, and other OTel platforms
- **Minimal overhead**: Efficient instrumentation with negligible performance impact
- **Works with all connection types**: HTTP, WebSocket, and embedded databases

### Learn More

For a complete example with configuration options and best practices, see [`examples/logfire/`](examples/logfire/).

## Spectron

[Spectron](https://github.com/surrealdb/spectron) is a memory service, and its
client is bundled with `surrealdb`. It is **no longer re-exported at the top
level** - import it from its own submodule:

```python
from surrealdb.spectron import Spectron, AsyncSpectron

with Spectron(
    context="acme-prod",
    endpoint="https://api.spectron.example",
    api_key="sk-spec-...",
) as memory:
    memory.remember("I work at Acme as CTO")
    hits = memory.recall("what do I do at Acme")
    print(hits.hits)
```

`Spectron` is synchronous (backed by `requests`); `AsyncSpectron` is the
`await`-able equivalent (backed by `aiohttp`). See
[`src/surrealdb/spectron/README.md`](src/surrealdb/spectron/README.md) for the
full client documentation.

## Contributing

Contributions to this library are welcome! If you encounter issues, have feature requests, or 
want to make improvements, feel free to open issues or submit pull requests.

If you want to contribute to the Github repo please read the general contributing guidelines on concepts such as how to create a pull requests [here](https://github.com/surrealdb/surrealdb.py/blob/main/CONTRIBUTING.md).

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
