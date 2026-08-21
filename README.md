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
    
    # Create (sync query() returns a builder - call .execute() to run it)
    db.query("""
    insert into person {
        user: 'me',
        password: 'very_safe',
        tags: ['python', 'documentation']
    };
    """).execute()

    # Read - .first() returns the first statement's result (the rows)
    print(db.query("select * from person").first())
    
    # Update
    print(db.query("""
    update person content {
        user: 'you',
        password: 'more_safe',
        tags: ['awesome']
    };
    """).execute())

    # Delete
    print(db.query("delete person").execute())
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

`select()` (async and sync) always runs eagerly and unwraps single records:

- `select(RecordID(...))` (or a `"table:id"` string) -> `dict[str, Value] | None`
  (`None` when the record does not exist)
- `select(Table(...))` (or a bare table-name string) -> `list[Value]`

```python
row = await db.select(RecordID("person", "tobie"))  # dict | None
rows = await db.select(Table("person"))             # list
```

#### What a `RecordID` and a `Table` accept

Both constructors check their arguments, so a mistake raises `TypeError` at the
line that made it rather than coming back from the server as `Parse error`.

A **table name** must be a `str`, and that is the only rule — SurrealDB accepts
any string, including one that is empty, has spaces, is unicode, starts with a
digit, or contains a colon.

A **record id** must be one of `str`, `int`, `uuid.UUID`, `list`, `tuple`,
`dict`, or a `Range` (see below). The union is exported as `RecordIdValue` if
you want to annotate against it. Notably rejected: `None`, `bool` (Python's
`bool` is an `int`, but SurrealDB has no boolean id), `float`, and `bytes` —
the server refuses all of them.

```python
RecordID("person", "tobie")     # ok
RecordID("person", ["a", 1])    # ok — composite ids are arrays or objects
RecordID(1, "tobie")            # TypeError: the arguments look swapped
Table(None)                     # TypeError: name must be a str
```

The check applies to values *you* construct. Records decoded from a response
bypass it, so that a future server sending an id type this SDK does not know
about still reads back — `RecordID.id` is therefore typed more widely than
`RecordIdValue`, and is not guaranteed to be one of the types above.

> Before 3.0.0, `Table(None)` was not rejected anywhere and
> `db.insert(Table(None), rows)` **succeeded**, writing to a table literally
> named `None`. If you have code that builds a table name dynamically, that is
> the case to check.

#### Selecting only some fields

Pass `fields=` to narrow the projection, so the server sends only what you ask
for rather than the whole record:

```python
await db.select(RecordID("person", "tobie"), fields=["name", "email"])
await db.select(Table("person"), fields=["address.city"])
```

A dot walks into a nested object. Each segment is escaped separately, so a field
name containing a space or unicode is quoted correctly and a field list can
never smuggle SurrealQL into the statement. A field whose name genuinely
*contains* a dot cannot be spelled this way — use `query()` for that.

`id` is not included unless you ask for it, exactly as in SurrealQL, so a model
passed to `into=` that declares an `id` field needs `fields=["id", ...]`.

Anything beyond a list of field names — aliases, functions, `WHERE`, `ORDER BY`
— is a `query()`, not a `select()`.

#### Record ranges

A `RecordID` whose id is a `Range` targets every record in that range, and every
CRUD method returns all of them — the same as the equivalent `"person:1..=3"`
string:

```python
from surrealdb import RecordID, Range, BoundIncluded, BoundExcluded

first_three = RecordID("person", Range(BoundIncluded(1), BoundIncluded(3)))
await db.select(first_three)            # every record in person:1..=3
await db.delete(first_three)            # deletes them all, returns them all
await db.select("person:1..=3")         # the same target, spelled as a string
```

Use `BoundExcluded` for `..` rather than `..=`, and `None` for an open end
(`Range(BoundIncluded(1), None)` is `person:1..`).

Two caveats. A range needs a table, so a bare `Range` is not a resource target —
`db.select(Range(...))` raises `SurrealError`; wrap it in a `RecordID`. And the
`@overload`s above resolve on the *static* type `RecordID`, which says nothing
about the id, so a type checker still reads `select(first_three)` as
`dict | None` while it returns a list at runtime. Cast, or use the string form,
if you need the narrower type.

### Mapping rows to a model (`into=`)

Pass the keyword-only `into=` argument to map each returned record onto a model
class - a dataclass, a pydantic `BaseModel`, or any class whose constructor
accepts the record's fields as keyword arguments. The return type is narrowed
precisely per overload: a single-record target resolves to `Model` (or
`Model | None`), a table target to `list[Model]`.

```python
from dataclasses import dataclass

@dataclass
class Person:
    id: RecordID
    name: str

# select: single record -> Person | None, table -> list[Person]
person = await db.select(RecordID("person", "tobie"), into=Person)  # Person | None
people = await db.select(Table("person"), into=Person)              # list[Person]

# create / update / upsert / delete map the written record(s) too
created = await db.create(RecordID("person", "tobie"), {"name": "Tobie"}, into=Person)
updated = await db.update(Table("person"), {"name": "Updated"}, into=Person)  # list[Person]

# insert maps the inserted records
inserted = await db.insert(Table("person"), [{"name": "A"}], into=Person)  # list[Person]

# the no-data builder form carries the model through its clause methods
p = await db.create(RecordID("person", "jaime"), into=Person).merge({"name": "Jaime"})

# map each ROW of a single query statement with into(Model, rows=True)
rows = await db.query("SELECT * FROM person").into(Person, rows=True)  # list[Person]
```

Sync connections take the same `into=` argument and run eagerly:

```python
person = db.select(RecordID("person", "tobie"), into=Person)  # Person | None
created = db.create(RecordID("person", "tobie"), {"name": "Tobie"}, into=Person)
rows = db.query("SELECT * FROM person").into(Person, rows=True)  # list[Person]
```

Omitting `into=` leaves the raw `dict` / `list[Value]` results completely
unchanged.

The model has to accept every field of the records it is given. `update(record,
data)` writes `data` as the record's whole content, so the example above leaves
each `person` with just `id` and `name` — write a field `Person` does not
declare and the mapping fails with an `UnexpectedResponseError` naming both
sides:

```
into=Person could not be built from this record: Person.__init__() got an
unexpected keyword argument 'active'. The record has ['active', 'id']; Person
accepts ['id', 'name'].
```

Give the extra fields defaults, add them to the model, or `SELECT` only the
columns it declares.

Sync usage is **eager** - there is no `await` to defer to, so the
connection methods run single-shot operations immediately and return the
plain result. A builder is only handed back for the deferred no-data form
so you can pick a clause; there are **no** magic methods, so a builder
never auto-executes on `bool()`, `==`, indexing, iteration, or attribute
access.

```python
from surrealdb import Surreal

with Surreal("ws://localhost:8000/rpc") as db:
    db.signin({"username": "root", "password": "root"})
    db.use("ns", "db")

    # Passing data runs immediately and returns the created record dict.
    tobie = db.create(RecordID("person", "tobie"), {"name": "Tobie"})

    # No-data form returns a builder; a terminal clause method runs it.
    out = db.create(RecordID("person", "alice")).merge({"name": "Alice"})

    # Clause-less run: call .execute() explicitly.
    empty = db.create(RecordID("person", "bob")).execute()

    # select() and delete() always run eagerly and return the result.
    row = db.select(RecordID("person", "tobie"))  # dict | None
    db.delete(RecordID("person", "bob"))

    # query() returns a builder; call .execute()/.first()/.into().
    db.query("DELETE person;").execute()
```

On 3.x, `DELETE` names a table that has to exist: `db.query("DELETE
temp_data;")` raises `NotFoundError: The table 'temp_data' does not exist`
rather than deleting nothing. (2.x returns an empty result instead — see
[Talking to a SurrealDB 2.x server](#talking-to-a-surrealdb-2x-server).) Use
`REMOVE TABLE IF EXISTS temp_data;` when you cannot be sure.

### Thread safety

The no-data sync builder guards its cache with a per-builder lock so
calling `.execute()` from multiple threads issues exactly one RPC. It is
**not** safe for concurrent *reconfiguration* though — calling `.merge()`
on one thread while another calls `.execute()` is a race on the builder's
clause/data state that the lock does not cover. Treat builders as
single-shot, single-owner values; pass the realised result between
threads, not the builder itself.

The underlying `BlockingWsSurrealConnection` is itself thread-safe (it
serialises send/recv with an internal lock), so sharing a connection
across threads and issuing per-thread operations against it is fine.

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

`query()` always returns a `list[Value]` - one entry per statement, even
for a single statement - so multi-statement queries and `BEGIN ... COMMIT`
blocks never silently drop results. Use `.first()` for the first
statement's result (or `None` when there are no statements).

```python
rows = await db.query("SELECT * FROM person")       # [people_list]
first = await db.query("SELECT * FROM person").first()  # people_list
many = await db.query(
    "SELECT * FROM person; SELECT count() FROM person GROUP ALL"
)
# many is [people_list, count_list]

# Sync: query() returns a builder - run it explicitly.
rows = db.query("SELECT * FROM person").execute()   # [people_list]
first = db.query("SELECT * FROM person").first()    # people_list
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

Or map each **row** of a single statement's result onto a model with
`.into(Model, rows=True)`, which returns `list[Model]`:

```python
people = await db.query("SELECT * FROM person").into(Person, rows=True)  # list[Person]
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
`AsyncSurrealTransaction` / `BlockingSurrealTransaction`, along with
`query_raw()`, `info()`, and `version()`. Every one of them scopes to the
session (and transaction) it was called on, so you never pass `session_id`
or `txn_id` by hand.

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

## `None`, `Null`, and empty values

SurrealDB has two ways for a field to hold nothing, and they are different
values:

| SurrealQL | meaning | Python |
| --------- | ------- | ------ |
| `NONE`    | the field is not there | `None` |
| `NULL`    | the field is there and is null | `surrealdb.Null` |

An unset `option<T>` column is NONE, and a NONE field does not appear in a
record at all when you read it. NULL is a value the field holds, and a column
has to be declared to permit it — `option<T>` alone does not, and rejects NULL.

```python
from surrealdb import Null

db.create(rec, {"age": None})    # age is NONE — what option<int> expects
db.create(rec, {"age": Null})    # age is NULL — rejected by option<int>
```

This matters most when you read a record and write it back. A NULL field reads
as `Null`, and sending `Null` back writes NULL again, so the round trip keeps
the field:

```python
row = db.select(rec)             # {"nickname": Null}
row["name"] = "new name"
db.update(rec, row)              # nickname is still NULL
```

`Null` is falsy, like `None`, so `if not row["nickname"]` reads the way you
would expect. It is deliberately **not** equal to `None` — the two are
different values to the server, and treating them as one is what used to make
the write-back above delete the field.

> Before 3.0.0-beta.5 a NULL field decoded to `None`, which encoded back to
> NONE — so an ordinary read-modify-write silently *removed* every NULL field
> it touched. If you have code comparing a database value with `is None`,
> check whether the column can be NULL.

**Sets read back as `SurrealSet`.** SurrealDB's `set<T>` is a deduplicated
sequence that accepts any member type, including `set<object>` and `set<array>`
— which a Python `set` cannot hold, because its members must be hashable.

`SurrealSet` is a `list` subclass, so it indexes and compares like the sequence
it is, and it encodes back under the set tag, so writing a record back keeps the
field a set:

```python
row = db.select(rec)                   # {"tags": SurrealSet(['a', 'b'])}
row["name"] = "new name"
db.update(rec, row)                    # tags is still a set

db.select(rec)["tags"] == ["a", "b"]   # True — it is a list
```

Writing a plain Python `set` still works and is still sent as a set. The order
is whatever the server sent: SurrealDB normalises a set, so `<set>[3,1,2]` comes
back as `[1, 2, 3]`.

> Decoding a set to a plain `list` — as 3.0.0-beta.5 briefly did — loses the
> type on the way back: a schemafull `set<T>` field rejects the array outright,
> and a schemaless one silently becomes an array and stops deduplicating.
>
> Sets need SurrealDB 3.x. 2.x has no CBOR set representation at all — see
> [Talking to a SurrealDB 2.x server](#talking-to-a-surrealdb-2x-server).

## Error handling

Every error the SDK raises derives from `SurrealError`, so a single
`except SurrealError` covers all of them regardless of transport.

Below that base, errors split into two branches that mean different things:

| Branch            | Meaning                                                     | Retry?                |
| ----------------- | ----------------------------------------------------------- | --------------------- |
| `ServerError`     | The server ran your request and rejected it                  | No — it will fail again |
| `TransportError`  | The request never produced a structured server response      | Maybe — it may succeed |

`ServerError` mirrors SurrealDB's structured error format, so you can match
on `kind` and read typed details rather than parsing messages:

```python
from surrealdb import Surreal
from surrealdb.errors import NotFoundError, ServerError, SurrealError, TransportError

with Surreal("ws://localhost:8000/rpc") as db:
    db.signin({"username": "root", "password": "root"})
    db.use("ns", "db")

    try:
        db.query("SELECT * FROM nonexistent:1").execute()
    except NotFoundError as error:
        print(error.kind, error.table_name)   # NotFound nonexistent
    except ServerError as error:
        print(error.kind, error.details)
    except TransportError as error:
        print("could not reach the server:", error)
```

### Talking to a SurrealDB 2.x server

Six things behave differently against SurrealDB 2.x, all because of what the
2.x server does rather than anything the SDK chooses.

**Error kinds need 3.x.** The subclasses below `ServerError` come from the
`kind` the server reports, and 2.x does not send one — its error payload has
only a generic `-32000` code and a message string. So every server-side failure
arrives as `InternalError`:

| | SurrealDB 3.x | SurrealDB 2.x |
| --- | --- | --- |
| `db.query("SELECT * FROM")` | `ValidationError` | `InternalError` |
| `db.query("THROW 'nope'")` | `ThrownError` | `InternalError` |

`except SurrealError` and `except ServerError` work on every version. A narrower
`except ThrownError` matches only on 3.x and will silently *not* match on 2.x,
so if you support both, catch the branch rather than the leaf, or read the
message with `str(error)`. The SDK cannot recover the classification — it is not sent.

**Python sets need 3.x.** Sets are encoded with SurrealDB 3.x's CBOR set tag.
2.x has no set representation at all — it returns SurrealQL sets as plain
arrays — and rejects anything carrying the tag. Send a `list` instead when
targeting 2.x; a list is what 2.x uses for a `set<…>` field anyway, and the
server deduplicates it. On 3.x a list is *not* interchangeable with a set: a
`set<…>` field rejects one.

**`let()` wins over a query's own variables on a 2.x websocket.** Passing a
variable to `query()` shadows a `let()` binding of the same name for that one
query — on 3.x, and on HTTP against any version, where the SDK replays `let()`
bindings itself. On a 2.x websocket `let()` is a server-side session binding and
that server resolves it the other way round:

```python
db.let("limit", 99)
db.query("RETURN $limit", {"limit": 5})   # 5, except on a 2.x websocket: 99
```

The SDK sends the same request in both cases, so there is nothing for it to fix
without knowing the server version up front. Use distinct names for session
bindings and per-query variables if you target 2.x over a websocket.

**A 2.x function body cannot read a variable from outside itself.** On 3.x a
stored function resolves `$v` from the session or from the query's parameters;
on 2.x it resolves neither, on any transport:

```python
db.query("DEFINE FUNCTION fn::readv() { RETURN $v; };").execute()
db.let("v", 42)
db.run("fn::readv")        # 42 on 3.x, None on 2.x
```

Pass the value as an argument (`db.run("fn::add", [1, 2])`) if you target 2.x —
arguments work on every version.

**`DELETE` on a table that does not exist is an error only on 3.x.** 3.x raises
`NotFoundError: The table 'temp_data' does not exist`; 2.x returns an empty
result, as though it had deleted nothing:

```python
db.query("DELETE temp_data;").execute()   # [[]] on 2.x, NotFoundError on 3.x
```

`REMOVE TABLE IF EXISTS temp_data;` behaves the same on both.

**A 2.x server does not tell subscribers that a live query was killed.** On 3.x
the server sends a `KILLED` notification and `subscribe_live()` ends, whoever
killed the query. On 2.x nothing is sent, so a subscriber to a query killed from
*another* connection simply stops hearing anything and keeps waiting — there is
no signal for the SDK to end the generator on. Calling `kill()` on the same
connection you subscribed from ends the subscription on every version.

The `TransportError` branch is `ConnectionUnavailableError` (the host was
unreachable or the socket closed), `TransportTimeoutError` (the request timed
out), and `HttpStatusError` (a non-2xx HTTP response, carrying `.status`,
`.body`, and `.url`). Each keeps the underlying library exception as
`__cause__` when you need the original detail.

Note that a non-2xx HTTP response is reported as `HttpStatusError` rather than
a `ServerError` subclass, because SurrealDB answers those at the HTTP layer
with a plain-text or JSON body and no structured RPC error to map. An invalid
bearer token over HTTP, for example, surfaces as `HttpStatusError` with
`.status == 401`, not `NotAllowedError`.

Invalid *inputs* are still rejected with plain `ValueError` / `TypeError`
before anything is sent, following normal Python convention.

## Migrating from 2.x

v3.0 is a breaking change. Highlights:

| 2.x                                              | 3.0                                                       |
| ------------------------------------------------ | --------------------------------------------------------- |
| `db.merge(record, data)`                         | `db.update(record).merge(data)`                           |
| `db.patch(record, data)`                         | `db.update(record).patch(data)`                           |
| `db.insert_relation(table, data)`                | `db.insert(table, data, relation=True)`                   |
| `db.query("RETURN 1")` -> single result          | `db.query("RETURN 1")` -> `[result]` (use `.first()` / `[0]`) |
| `db.query("RETURN 1; RETURN 2")` -> first result | `db.query("RETURN 1; RETURN 2")` -> `list` of all results |
| n/a                                              | `db.run("fn::name", [args])`                              |
| n/a                                              | `db.query("...").into(MyDataclass)`                       |
| Sync `db.query("DELETE foo")` runs immediately   | Sync `db.query("DELETE foo").execute()` (returns list)     |
| Sync `db.create(rec)[...]` (magic auto-exec)     | Sync `db.create(rec, data)` eager, or `db.create(rec).execute()` |
| `db.select(RecordID(...))` -> `[record]`         | `db.select(RecordID(...))` -> `record` dict or `None`     |
| `db.delete("my-table")` (silently inlined)       | `db.delete(Table("my-table"))` (raw string rejected)      |
| A NULL field read as `None`                      | A NULL field reads as `Null` (`None` still means NONE)    |
| `set<T>` read as a Python `set`                  | `set<T>` reads as a `SurrealSet` (writing a `set` is unchanged) |

> Bare-string resource targets are now strictly validated against the
> safe-identifier pattern (`[A-Za-z_][A-Za-z0-9_]*`) so user-supplied
> strings can never be concatenated into the generated SurrealQL. Names
> with hyphens, spaces, or other special characters must be wrapped in
> `Table(...)` or `RecordID(...)`, both of which are parameter-bound.

## Embedded Database

SurrealDB can also run embedded directly within your Python application natively. This provides a fully-featured database without needing a separate server process.

### Installation

The embedded database ships as an optional native extension, `surrealdb-embedded`,
so it is **not** part of the default install. Request it with the `embedded` extra:

```bash
pip install 'surrealdb[embedded]'
```

Or install using `uv`:

```bash
uv add 'surrealdb[embedded]'
```

Without the extra, an embedded URL raises `UnsupportedEngineError` telling you to
install it - the remote `http://`, `https://`, `ws://` and `wss://` connections work
either way.

Embedded connections do not authenticate: there is no server and no root user, so
calling `signin()` on one raises `NotAllowedError`. Use `use()` to select a namespace
and database and start querying.

For source builds, you'll need Rust toolchain and maturin:

```sh
uv run maturin develop --release --manifest-path embedded/Cargo.toml
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
    
    person = db.create("person", {"name": "Jane"})
    print(person)

# File-based
with Surreal("file://mydb") as db:
    db.use("test", "test")
    
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

For more examples, see the [`examples/embedded/`](https://github.com/surrealdb/surrealdb.py/tree/main/examples/embedded) directory.

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

For a complete example with configuration options and best practices, see [`examples/logfire/`](https://github.com/surrealdb/surrealdb.py/tree/main/examples/logfire).

## Files

SurrealDB can store files in a bucket - in memory, on disk, or on object storage
such as S3. A `File` is a *reference* to one: a bucket plus a key. It holds no
bytes and is not a Python file object.

Buckets are currently an experimental server feature, so the server has to be
started with `SURREAL_CAPS_ALLOW_EXPERIMENTAL=files`, and a bucket has to exist:

```surql
DEFINE BUCKET images BACKEND "memory";
```

```python
from surrealdb import File, Surreal

with Surreal("ws://localhost:8000/rpc") as db:
    db.signin({"username": "root", "password": "root"})
    db.use("ns", "db")

    avatar = File("images", "/photos/avatar.png")

    db.files.put(avatar, png_bytes)          # upload, replacing anything there
    png_bytes = db.files.get(avatar)         # -> bytes, or None if absent

    meta = db.files.head(avatar)             # -> FileMetadata | None
    print(meta.size, meta.updated)

    for entry in db.files.list("images", prefix="/photos", limit=50):
        print(entry.file.key, entry.size)
```

`db.files` is available on all six connection classes, and on sessions and
transactions too - `txn.files.put(...)` runs inside that transaction. The async
classes take the same calls with `await`.

| Method | Returns |
| --- | --- |
| `put(file, content)` | `None`, replacing anything at that key |
| `put_if_not_exists(file, content)` | `None`; writes only if the key is free |
| `get(file)` | `bytes`, or `None` if the file does not exist |
| `exists(file)` | `bool` |
| `delete(file)` | `None`; deleting an absent file is not an error |
| `head(file)` | `FileMetadata`, or `None` if absent |
| `list(bucket, *, limit=, prefix=, start=)` | `list[FileMetadata]`; `start` is exclusive |
| `copy(source, target)` / `copy_if_not_exists` | `None` |
| `rename(file, key)` / `rename_if_not_exists` | `None`; `key` is a `str`, within the same bucket |

A key is normalised to start with `/`, so `File("b", "a.txt")` and
`File("b", "/a.txt")` are the same file.

#### Why files are bound, not written into queries

SurrealQL's file literal - `f"bucket:/key"` - accepts only
`[A-Za-z0-9_-./]`, and there is **no escape mechanism**. A key containing a
space, an accent or an emoji cannot be written as a literal at all:

```
Parse error: Unexpected character ` `, file strings key's only allow alpha
numeric characters and `_`, `-`, `.`, and `/`
```

Every `db.files` method binds the `File` as a query parameter instead, which
carries any key. `str(File(...))` renders the literal form for logging, but is
display-only - use `File.is_literal_safe()` if you need to know whether a
given file could be written into a query, and bind it rather than interpolating
it either way.

## Agent memory

Agent memory is an optional client for [Spectron](https://github.com/surrealdb/spectron),
a memory service. It ships as its own distribution so it can move at its own
pace, and is installed through an extra:

```sh
pip install 'surrealdb[memory]'

# Using uv
uv add 'surrealdb[memory]'
```

```python
from surrealdb.memory import AsyncMemory, Memory

with Memory(
    context="acme-prod",
    endpoint="https://api.spectron.example",
    api_key="sk-spec-...",
) as memory:
    memory.remember("I work at Acme as CTO")
    hits = memory.recall("what do I do at Acme")
    print(hits.hits)
```

`Memory` is synchronous (backed by `requests`); `AsyncMemory` is the
`await`-able equivalent (backed by `aiohttp`). Errors derive from
`MemoryServiceError` — not `MemoryError`, which is a Python builtin. See
[`memory/README.md`](https://github.com/surrealdb/surrealdb.py/blob/main/memory/README.md)
for the full client documentation.

Without the extra, `surrealdb.memory` still imports, and any attribute names the
missing package:

```
ImportError: 'Memory' needs the agent memory client, which ships separately.
    pip install 'surrealdb[memory]'    # or: uv add 'surrealdb[memory]'
```

Because it is a separate distribution, its version moves independently of the
SDK's — you can hold `surrealdb` at 3.x and upgrade `surrealdb-memory` across
its own majors.

## Contributing

Contributions to this library are welcome! If you encounter issues, have feature requests, or 
want to make improvements, feel free to open issues or submit pull requests.

If you want to contribute to the Github repo please read the general contributing guidelines on concepts such as how to create a pull requests [here](https://github.com/surrealdb/surrealdb.py/blob/main/CONTRIBUTING.md).

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](https://github.com/surrealdb/surrealdb.py/blob/main/LICENSE) file for details.
