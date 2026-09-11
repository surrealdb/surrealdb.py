"""Streaming query results with the blocking client.

Two things are worth separating, because only one of them needs any code:

* **Ordinary queries already stream.** Against SurrealDB v3.3.0 or later over a
  websocket, ``query()``, ``select()``, ``create()`` and every builder ask for
  their answer as a sequence of frames and rebuild it as it arrives. Nothing to
  switch on, and the answer is identical.
* **Streaming to *you*** is what ``.stream()`` adds: the rows reach your loop as
  the server produces them, instead of all together at the end.

Run with a server on ``ws://localhost:8000``:

    python examples/streaming/basic_sync.py
"""

import time
from dataclasses import dataclass

from surrealdb import RecordID, Surreal
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


def seed(db: Surreal) -> None:
    db.query(
        """
        DEFINE TABLE IF NOT EXISTS person;
        DELETE person;
        CREATE |person:2000| SET name = 'someone' RETURN NONE;
        """
    )


def the_whole_answer(db: Surreal) -> None:
    """`.execute()` gives you everything, once the query has finished.

    The same query as `.stream()` uses below, so the two timings compare.
    """
    started = time.monotonic()
    statements = db.query(SLOW_QUERY).execute()
    print(
        f"  .execute()                 -> {len(statements[0])} rows, "
        f"none of them before {time.monotonic() - started:.2f}s"
    )


def rows_as_they_arrive(db: Surreal) -> None:
    """`.stream()` gives you each row as the server produces it.

    Iterating is flat across statements, so this counts one more than the
    `.execute()` above did: the `SLEEP` is a statement too, and its (empty)
    value arrives as a row. `.statements()` below keeps them apart.
    """
    started = time.monotonic()
    first_at: float | None = None
    seen = 0

    for _person in db.query(SLOW_QUERY).stream():
        if first_at is None:
            first_at = time.monotonic() - started
        seen += 1

    print(
        f"  .stream()                  -> {seen} rows, "
        f"first one at {first_at:.2f}s, last at {time.monotonic() - started:.2f}s"
    )


def rows_as_models(db: Surreal) -> None:
    """`into=` maps each row as it arrives, so nothing is held whole."""
    people: list[Person] = []

    for person in db.select("person", fields=["id", "name"]).stream(into=Person):
        people.append(person)

    print(f"  .stream(into=Person)       -> {len(people)} Person instances")
    print(f"                                first: {people[0]}")


def stopping_early(db: Surreal) -> None:
    """Leaving the loop asks the server to abandon the rest of the query.

    Use ``with`` (or call ``close()``): that is what stops the query at
    the moment you choose rather than whenever the iterator is collected.
    """
    started = time.monotonic()

    with db.query(SLOW_QUERY).stream() as stream:
        for person in stream:
            print(f"  found {person['name']!r}, stopping there")
            break

    print(
        f"  returned after {time.monotonic() - started:.2f}s, with the query's "
        "SLEEP still to run"
    )


def one_result_per_statement(db: Surreal) -> None:
    """`.statements()` is the other view: one completed result per statement."""
    query = db.query(
        "SELECT * FROM person LIMIT 3; SELECT count() FROM person GROUP ALL"
    )

    for statement in query.stream().statements():
        kind = "rows" if isinstance(statement.value, list) else "value"
        print(f"  statement {statement.index}: {kind}, took {statement.time}")


def when_the_server_cannot_stream(db: Surreal) -> None:
    """Everything above works on any server, which is the point of the fallback.

    Against a server older than v3.3.0, or over HTTP, the query runs the
    buffered way and its rows are handed back one at a time - so the code does
    not change. Pass ``require_streaming=True`` when that trade is wrong for
    you, and you get told instead of served a fallback.
    """
    try:
        for _ in db.query("SELECT * FROM person LIMIT 1").stream(
            require_streaming=True
        ):
            print("  require_streaming=True -> this server streams")
            break
    except UnsupportedFeatureError as error:
        print(f"  require_streaming=True -> refused: {error}")


def main() -> None:
    with Surreal(URL) as db:
        db.signin({"username": "root", "password": "root"})
        db.use("example", "streaming")
        seed(db)

        print("The whole answer, when the query finishes:")
        the_whole_answer(db)

        print("\nRows as the server produces them:")
        rows_as_they_arrive(db)

        print("\nRows mapped onto a model:")
        rows_as_models(db)

        print("\nStopping early:")
        stopping_early(db)

        print("\nOne result per statement:")
        one_result_per_statement(db)

        print("\nWhen streaming is not available:")
        when_the_server_cannot_stream(db)


if __name__ == "__main__":
    main()
