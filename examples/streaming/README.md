# Streaming Query Examples

How to read a query's rows as the server produces them, rather than all together
when it finishes.

Two things are worth separating, because only one of them needs any code:

- **Ordinary queries already stream.** Against SurrealDB **v3.3.0 or later** over
  a websocket, `query()`, `select()`, `create()`, `upsert()` and every builder
  ask for their answer as a sequence of frames and rebuild it as it arrives.
  Nothing to switch on, and the answer is identical — so there is nothing to
  change in existing code.
- **Streaming to _you_** is what `.stream()` adds: each row reaches your loop as
  it is produced, you can stop early, and you never have to hold the whole
  answer.

The difference is not subtle. Both scripts print it, using the same query
(`SELECT * FROM person ORDER BY id; SLEEP 2s`) over 2,000 records:

```
  await / .execute()         -> 2000 rows, none of them before 2.00s
  .stream()                  -> 2001 rows, first one at 0.00s, last at 2.01s
```

Same frames on the wire either way. What changes is whether the client hands
them to you as they land or accumulates them first.

## Examples

### `basic_async.py`

Streaming with the async client:

- `await db.query(...)` — the whole answer, which already streams underneath
- `.stream()` — rows as they arrive, with the timings above
- `.stream(into=Person)` — each row mapped onto a model as it arrives, so a
  large table is read one model at a time and never held whole
- `async with ... break` — stopping early, which asks the server to abandon the
  rest of the query
- `.statements()` — one completed result per statement, for multi-statement
  queries
- `require_streaming=True` — be told rather than served the buffered fallback

Run with:

```bash
python examples/streaming/basic_async.py
```

### `basic_sync.py`

The same six things on the blocking client, with `with` instead of `async with`
and `.execute()` where the async form awaits.

Run with:

```bash
python examples/streaming/basic_sync.py
```

## It works on every server and transport

Streaming needs a websocket and v3.3.0 or later. Everywhere else — an older
server, a server whose capabilities deny the `query_stream` RPC, HTTP, or the
embedded engine — the query runs the buffered way and its rows are handed back
one at a time. **The code does not change**, which is the point: one path works
everywhere.

That fallback gives up the two things streaming is for, so when it matters pass
`require_streaming=True` and get an `UnsupportedFeatureError` instead of a quiet
buffered answer. The error says *which* case it was, because upgrading fixes a
server that lacks the method and not one that denies it.

## Two caveats worth knowing

- **Rows are provisional until iteration ends.** A row is delivered before the
  statement that produced it has finished — that is the point — so a statement
  that fails *after* emitting rows raises, and the rows it already yielded are
  void. `.statements()` narrows this to per-statement, and awaiting the builder
  is the all-or-nothing view.
- **Keep up, or memory grows.** The protocol has no per-stream flow control, so
  a consumer slower than the server accumulates rows until it catches up. If the
  work per row is slow, use `.statements()`, or stop the stream and page
  instead.

Both are covered in more depth in the [main README's streaming
section](../../README.md#streaming-queries).

## Setup

Start a server:

```bash
surreal start --user root --pass root memory
```

Then run either script. They sign in as `root`, use the `example` / `streaming`
namespace and database, and seed 2,000 records into a `person` table.
