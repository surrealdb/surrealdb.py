"""Every ``db.<method>()`` in ``examples/`` names a method that exists.

The 3.0 release removed ``db.merge(record, data)`` in favour of
``db.update(record).merge(data)`` and documented the change in the README's own
migration table - but every framework example kept calling the old form. Eleven
files across fastapi, flask, quart, starlette, sanic, litestar, django, graphql,
fastmcp, logfire and the Jupyter notebooks, all of which fail with
``AttributeError`` the moment someone runs the example the docs point them at.

Nothing imports or executes the examples, so nothing noticed. This does not run
them either - most need a framework installed and a server up - but it does
read them, which is enough to catch a method that no longer exists.

Notebooks are included: the same call was in one of those too.
"""

import ast
import inspect
import json
import pathlib
import re

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

_CONNECTIONS: list[type] = [
    BlockingWsSurrealConnection,
    AsyncWsSurrealConnection,
    BlockingHttpSurrealConnection,
    AsyncHttpSurrealConnection,
]

# The embedded classes need the optional native extension, which most CI legs
# do not install. They inherit the websocket API, so leaving them out narrows
# the accepted set rather than widening it - a missing method is still caught.
try:
    from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
    from surrealdb.connections.blocking_embedded import (
        BlockingEmbeddedSurrealConnection,
    )
except ImportError:  # pragma: no cover - depends on how the SDK was installed
    pass
else:
    _CONNECTIONS += [BlockingEmbeddedSurrealConnection, AsyncEmbeddedSurrealConnection]

_EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "examples"

# Examples spell their connection `db` throughout, so this finds the calls
# without needing to resolve names.
_DB_CALL = re.compile(r"\bdb\.([A-Za-z_]\w*)\s*\(")


def _public_api() -> set[str]:
    """Every public method reachable on a connection, whichever kind it is."""
    return {
        name for cls in _CONNECTIONS for name in dir(cls) if not name.startswith("_")
    }


def _sources() -> list[tuple[pathlib.Path, str]]:
    """Every example source, with notebook code cells flattened into text."""
    found: list[tuple[pathlib.Path, str]] = []
    for path in sorted(_EXAMPLES.rglob("*.py")):
        found.append((path, path.read_text()))
    for path in sorted(_EXAMPLES.rglob("*.ipynb")):
        notebook = json.loads(path.read_text())
        code = "\n".join(
            "".join(cell.get("source", ""))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        )
        found.append((path, code))
    return found


def test_the_examples_directory_was_found() -> None:
    """Guards the whole file against silently checking nothing."""
    sources = _sources()
    assert len(sources) > 20, f"only found {len(sources)} example sources"
    assert any("db.select(" in text for _, text in sources)


def test_no_example_calls_a_method_that_does_not_exist() -> None:
    api = _public_api()
    missing: dict[str, list[str]] = {}

    for path, text in _sources():
        for match in _DB_CALL.finditer(text):
            method = match.group(1)
            if method not in api:
                missing.setdefault(method, []).append(
                    str(path.relative_to(_EXAMPLES.parent))
                )

    assert not missing, "examples call methods the SDK does not have: " + "; ".join(
        f"db.{method}() in {', '.join(sorted(set(files)))}"
        for method, files in sorted(missing.items())
    )


def test_every_example_parses() -> None:
    """An example that is not valid Python cannot be run by anyone."""
    broken: list[str] = []
    for path, text in _sources():
        try:
            ast.parse(text)
        except SyntaxError as error:
            broken.append(f"{path.name}: {error}")

    assert not broken, "examples that do not parse: " + "; ".join(broken)


def _coroutine_methods() -> set[str]:
    """Public methods that are coroutines on any async connection class."""
    return {
        name
        for cls in _CONNECTIONS
        for name, member in vars(cls).items()
        if not name.startswith("_") and inspect.iscoroutinefunction(member)
    }


def test_no_example_iterates_a_coroutine() -> None:
    """``async for`` over an un-awaited coroutine raises ``TypeError``.

    ``subscribe_live`` is a coroutine that *returns* an async generator, so it
    has to be awaited before it can be iterated. Six framework examples wrote

        async for result in db.subscribe_live(live_query_id):

    which raises ``TypeError: 'async for' requires an object with __aiter__
    method, got coroutine`` the moment the endpoint is hit - so every
    live-query WebSocket example never delivered a single update.

    The existing check above only asks whether the method exists, which this
    passes: `subscribe_live` is real, it is just being used wrongly. Iterating
    a coroutine is wrong for any connection type, so this needs no guess about
    which one an example holds.
    """
    coroutines = _coroutine_methods()
    offenders: list[str] = []

    for path, text in _sources():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue  # reported by the parse test above
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFor):
                continue
            call = node.iter
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if not isinstance(func, ast.Attribute) or func.attr not in coroutines:
                continue
            offenders.append(
                f"{path.relative_to(_EXAMPLES.parent)}:{node.lineno} "
                f"iterates db.{func.attr}() without awaiting it"
            )

    assert not offenders, "examples iterating a coroutine: " + "; ".join(offenders)
