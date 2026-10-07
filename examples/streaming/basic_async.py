"""Streaming query results with the async client.

Two things are worth separating, because only one of them needs any code:

* **Ordinary queries already stream.** Against SurrealDB v3.3.0 or later over a
  websocket, ``query()``, ``select()``, ``create()`` and every builder ask for
  their answer as a sequence of frames and rebuild it as it arrives. Nothing to
  switch on, and the answer is identical.
* **Streaming to *you*** is what ``.rows()`` adds: the rows reach your loop as
  the server produces them, instead of all together at the end.

Run with a server on ``ws://localhost:8000``:

    python examples/streaming/basic_async.py
"""

import asyncio
import time
from dataclasses import dataclass

from surrealdb import (
    AsyncSurreal,
    DoneFrame,
    ErrorFrame,
    RecordID,
    ValueFrame,
)
from surrealdb.errors import UnsupportedFeatureError

URL = "ws://localhost:8000/rpc"

# A trailing SLEEP keeps the query running after its rows are produced, which is
# what makes the difference below visible rather than theoretical.
SLOW_QUERY = "SELECT * FROM person ORDER BY id; SLEEP 2s"


@dataclass
class Person:
    """The model rows are mapped onto by `stream(into=...)`."""

    id: RecordID
    name: str


async def seed(db: AsyncSurreal) -> None:
    await db.query(
        """
        DEFINE TABLE IF NOT EXISTS person;
        DELETE person;
        CREATE |person:2000| SET name = 'someone' RETURN NONE;
        """
    )


async def the_whole_answer(db: AsyncSurreal) -> None:
    """`await` gives you everything, once the query has finished.

    The same query as `.rows()` uses below, so the two timings compare.
    """
    started = time.monotonic()
    statements = await db.query(SLOW_QUERY)
    print(
        f"  await                      -> {len(statements[0])} rows, "
        f"none of them before {time.monotonic() - started:.2f}s"
    )


async def rows_as_they_arrive(db: AsyncSurreal) -> None:
    """`.rows()` gives you each row as the server produces it.

    Iterating is flat across statements: a statement with a single value, like
    `RETURN 42`, is one row, and one whose value is NONE, like the `SLEEP`
    here, is no rows at all. `.statements()` below keeps the statements apart.
    """
    started = time.monotonic()
    first_at: float | None = None
    seen = 0

    async for _person in db.query(SLOW_QUERY).rows():
        if first_at is None:
            first_at = time.monotonic() - started
        seen += 1

    print(
        f"  .rows()                  -> {seen} rows, "
        f"first one at {first_at:.2f}s, last at {time.monotonic() - started:.2f}s"
    )


async def rows_as_models(db: AsyncSurreal) -> None:
    """`into=` maps each row as it arrives, so nothing is held whole."""
    people: list[Person] = []

    async for person in db.select("person", fields=["id", "name"]).rows(into=Person):
        people.append(person)

    print(f"  .rows(into=Person)       -> {len(people)} Person instances")
    print(f"                                first: {people[0]}")


async def stopping_early(db: AsyncSurreal) -> None:
    """Leaving the loop asks the server to abandon the rest of the query.

    Use ``async with`` (or call ``aclose()``): that is what stops the query at
    the moment you choose rather than whenever the iterator is collected.
    """
    started = time.monotonic()

    async with db.query(SLOW_QUERY).rows() as stream:
        async for person in stream:
            print(f"  found {person['name']!r}, stopping there")
            break

    print(
        f"  returned after {time.monotonic() - started:.2f}s, with the query's "
        "SLEEP still to run"
    )


async def one_result_per_statement(db: AsyncSurreal) -> None:
    """`.statements()` is the other view: one completed result per statement."""
    query = db.query(
        "SELECT * FROM person LIMIT 3; SELECT count() FROM person GROUP ALL"
    )

    async for statement in query.statements():
        kind = "rows" if isinstance(statement.value, list) else "value"
        print(f"  statement {statement.index}: {kind}, took {statement.time}")


async def when_the_server_cannot_stream(db: AsyncSurreal) -> None:
    """Everything above works on any server, which is the point of the fallback.

    Against a server older than v3.3.0, or over HTTP, the query runs the
    buffered way and its rows are handed back one at a time - so the code does
    not change. Pass ``require_streaming=True`` when that trade is wrong for
    you, and you get told instead of served a fallback.
    """
    try:
        async for _ in db.query("SELECT * FROM person LIMIT 1").rows(
            require_streaming=True
        ):
            print("  require_streaming=True -> this server streams")
            break
    except UnsupportedFeatureError as error:
        print(f"  require_streaming=True -> refused: {error}")


async def frames_when_a_statement_fails(db: AsyncSurreal) -> None:
    """`.stream()` is the low-level view: one statement can fail and the rest go on.

    `rows()` and `statements()` both stop at the first failure. This does not -
    which is the only reason to reach for frames.
    """
    sql = "SELECT * FROM person LIMIT 2; THROW 'nope'; RETURN 42"

    async for frame in db.query(sql).stream():
        if isinstance(frame, ValueFrame):
            print(f"  statement {frame.index}: value {frame.value!r}")
        elif isinstance(frame, ErrorFrame):
            print(f"  statement {frame.index}: failed - {frame.error}")
        elif isinstance(frame, DoneFrame):
            print(f"  statement {frame.index}: complete in {frame.result.time}")


async def main() -> None:
    async with AsyncSurreal(URL) as db:
        await db.signin({"username": "root", "password": "root"})
        await db.use("example", "streaming")
        await seed(db)

        print("The whole answer, when the query finishes:")
        await the_whole_answer(db)

        print("\nRows as the server produces them:")
        await rows_as_they_arrive(db)

        print("\nRows mapped onto a model:")
        await rows_as_models(db)

        print("\nStopping early:")
        await stopping_early(db)

        print("\nOne result per statement:")
        await one_result_per_statement(db)

        print("\nFrames, when a statement fails:")
        await frames_when_a_statement_fails(db)

        print("\nWhen streaming is not available:")
        await when_the_server_cannot_stream(db)


if __name__ == "__main__":
    asyncio.run(main())
