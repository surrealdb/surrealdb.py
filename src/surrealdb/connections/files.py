"""Typed helpers over SurrealDB's ``file::*`` functions.

Reached as ``db.files`` on any connection, and on a session or transaction too -
``txn.files.put(...)`` runs inside that transaction. That works because these
helpers hold a *query runner* rather than a connection: a session and a
transaction each expose ``query()`` with their own id already bound, so nothing
here has to thread ``session_id`` or ``txn_id`` through eleven methods.

Every method binds the ``File`` as a parameter rather than writing it into the
query. That is not a style preference: SurrealQL's ``f"bucket:/key"`` literal
accepts only ``[A-Za-z0-9_-./]`` and has no escape mechanism, so a key with a
space, an accent or an emoji cannot be written as a literal at all. Bound, every
key works - see ``surrealdb.data.types.file`` for the parser's own wording.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# Imported at runtime, not under TYPE_CHECKING: `FileMetadata` is a dataclass, so
# its annotations are evaluated by `typing.get_type_hints` - which the public
# annotations guard does for every exported name - and a name that only exists
# for type checkers raises `NameError` there.
from surrealdb.data.types.datetime import PreciseDatetime
from surrealdb.data.types.file import File
from surrealdb.errors import UnexpectedResponseError

__all__ = ["AsyncFiles", "BlockingFiles", "FileMetadata"]


@dataclass(frozen=True)
class FileMetadata:
    """What ``head`` and ``list`` report about one stored file."""

    file: File
    size: int
    updated: PreciseDatetime | None


class _QueryRunner(Protocol):
    def query(self, query: str, vars: dict[str, Any] | None = ...) -> Any: ...


def _metadata(raw: Any) -> FileMetadata:
    """Turn one ``{file, size, updated}`` object into a ``FileMetadata``.

    The ``file`` arrives already decoded - it is CBOR tag 55, which the codec
    handles - and ``updated`` is tag 12, which it already handled before files
    existed. So this only reshapes; it does not parse.
    """
    if not isinstance(raw, dict) or "file" not in raw:
        raise UnexpectedResponseError(
            f"expected file metadata with a 'file' key, got {raw!r}"
        )
    return FileMetadata(
        file=raw["file"], size=raw.get("size", 0), updated=raw.get("updated")
    )


def _list_options(
    limit: int | None, prefix: str | None, start: str | None
) -> dict[str, Any]:
    """Build ``file::list``'s options object from explicit arguments.

    Explicit parameters rather than a passthrough ``dict`` because the server
    *silently ignores* option keys it does not recognise - a probe with
    ``{"nonsense": 1}`` returned the whole bucket. A caller who typed ``limti=2``
    against a dict-shaped API would get every file and no indication why, so the
    misspelling is caught here by Python instead.
    """
    options: dict[str, Any] = {}
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"limit must be an int, not {type(limit).__name__}")
        if limit < 1:
            raise ValueError(f"limit must be positive, got {limit}")
        options["limit"] = limit
    for name, value in (("prefix", prefix), ("start", start)):
        if value is not None:
            if not isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise TypeError(f"{name} must be a str, not {type(value).__name__}")
            options[name] = value
    return options


def _check_file(value: object, argument: str = "file") -> None:
    if not isinstance(value, File):
        raise TypeError(
            f"{argument} must be a surrealdb.File, not {type(value).__name__}: "
            f"{value!r}"
        )


def _check_key(value: object) -> None:
    """``file::rename``'s second argument is a key, not a file.

    Passing a ``File`` there fails server-side with "Incorrect arguments for
    function file::rename(). Argument 2 was..."; refusing it here says which
    argument and why, at the call that made the mistake.
    """
    if isinstance(value, File):
        raise TypeError(
            "key must be a str, not a File - rename moves within the same "
            f"bucket, so pass the new key: files.rename(file, {value.key!r})"
        )
    if not isinstance(value, str):
        raise TypeError(f"key must be a str, not {type(value).__name__}: {value!r}")


class BlockingFiles:
    """``db.files`` on a blocking connection, session or transaction."""

    __slots__ = ("_runner",)

    def __init__(self, runner: _QueryRunner) -> None:
        self._runner = runner

    def _first(self, query: str, vars: dict[str, Any]) -> Any:
        return self._runner.query(query, vars).first()

    def put(self, file: File, content: bytes) -> None:
        """Write ``content``, replacing anything already at that key."""
        _check_file(file)
        self._first("RETURN file::put($f, $c)", {"f": file, "c": content})

    def put_if_not_exists(self, file: File, content: bytes) -> None:
        """Write ``content`` only if the key is free; otherwise do nothing.

        The server neither writes nor complains when the file already exists.
        """
        _check_file(file)
        self._first("RETURN file::put_if_not_exists($f, $c)", {"f": file, "c": content})

    def get(self, file: File) -> bytes | None:
        """The file's bytes, or ``None`` if it does not exist."""
        _check_file(file)
        return self._first("RETURN file::get($f)", {"f": file})

    def exists(self, file: File) -> bool:
        _check_file(file)
        return bool(self._first("RETURN file::exists($f)", {"f": file}))

    def delete(self, file: File) -> None:
        """Remove the file. Deleting one that is already gone is not an error."""
        _check_file(file)
        self._first("RETURN file::delete($f)", {"f": file})

    def head(self, file: File) -> FileMetadata | None:
        """Size and last-modified time, or ``None`` if the file does not exist."""
        _check_file(file)
        raw = self._first("RETURN file::head($f)", {"f": file})
        return None if raw is None else _metadata(raw)

    def list(
        self,
        bucket: str,
        *,
        limit: int | None = None,
        prefix: str | None = None,
        start: str | None = None,
    ) -> list[FileMetadata]:
        """Every file in ``bucket``, newest options applied server-side.

        ``start`` is exclusive - listing from ``"/b.txt"`` returns what follows
        it, not itself. Raises if the bucket does not exist, which is the
        server's behaviour and worth surfacing rather than flattening to ``[]``:
        an empty bucket and a missing one are different mistakes.
        """
        if not isinstance(bucket, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"bucket must be a str, not {type(bucket).__name__}")
        options = _list_options(limit, prefix, start)
        if options:
            raw = self._first("RETURN file::list($b, $o)", {"b": bucket, "o": options})
        else:
            raw = self._first("RETURN file::list($b)", {"b": bucket})
        return [_metadata(entry) for entry in (raw or [])]

    def copy(self, source: File, target: File) -> None:
        _check_file(source, "source")
        _check_file(target, "target")
        self._first("RETURN file::copy($s, $t)", {"s": source, "t": target})

    def copy_if_not_exists(self, source: File, target: File) -> None:
        _check_file(source, "source")
        _check_file(target, "target")
        self._first(
            "RETURN file::copy_if_not_exists($s, $t)", {"s": source, "t": target}
        )

    def rename(self, file: File, key: str) -> None:
        """Move ``file`` to ``key`` within the same bucket."""
        _check_file(file)
        _check_key(key)
        self._first("RETURN file::rename($f, $k)", {"f": file, "k": key})

    def rename_if_not_exists(self, file: File, key: str) -> None:
        _check_file(file)
        _check_key(key)
        self._first("RETURN file::rename_if_not_exists($f, $k)", {"f": file, "k": key})


class AsyncFiles:
    """``db.files`` on an async connection, session or transaction."""

    __slots__ = ("_runner",)

    def __init__(self, runner: _QueryRunner) -> None:
        self._runner = runner

    async def _first(self, query: str, vars: dict[str, Any]) -> Any:
        return await self._runner.query(query, vars).first()

    async def put(self, file: File, content: bytes) -> None:
        """Write ``content``, replacing anything already at that key."""
        _check_file(file)
        await self._first("RETURN file::put($f, $c)", {"f": file, "c": content})

    async def put_if_not_exists(self, file: File, content: bytes) -> None:
        """Write ``content`` only if the key is free; otherwise do nothing."""
        _check_file(file)
        await self._first(
            "RETURN file::put_if_not_exists($f, $c)", {"f": file, "c": content}
        )

    async def get(self, file: File) -> bytes | None:
        """The file's bytes, or ``None`` if it does not exist."""
        _check_file(file)
        return await self._first("RETURN file::get($f)", {"f": file})

    async def exists(self, file: File) -> bool:
        _check_file(file)
        return bool(await self._first("RETURN file::exists($f)", {"f": file}))

    async def delete(self, file: File) -> None:
        """Remove the file. Deleting one that is already gone is not an error."""
        _check_file(file)
        await self._first("RETURN file::delete($f)", {"f": file})

    async def head(self, file: File) -> FileMetadata | None:
        """Size and last-modified time, or ``None`` if the file does not exist."""
        _check_file(file)
        raw = await self._first("RETURN file::head($f)", {"f": file})
        return None if raw is None else _metadata(raw)

    async def list(
        self,
        bucket: str,
        *,
        limit: int | None = None,
        prefix: str | None = None,
        start: str | None = None,
    ) -> list[FileMetadata]:
        """Every file in ``bucket``. ``start`` is exclusive."""
        if not isinstance(bucket, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"bucket must be a str, not {type(bucket).__name__}")
        options = _list_options(limit, prefix, start)
        if options:
            raw = await self._first(
                "RETURN file::list($b, $o)", {"b": bucket, "o": options}
            )
        else:
            raw = await self._first("RETURN file::list($b)", {"b": bucket})
        return [_metadata(entry) for entry in (raw or [])]

    async def copy(self, source: File, target: File) -> None:
        _check_file(source, "source")
        _check_file(target, "target")
        await self._first("RETURN file::copy($s, $t)", {"s": source, "t": target})

    async def copy_if_not_exists(self, source: File, target: File) -> None:
        _check_file(source, "source")
        _check_file(target, "target")
        await self._first(
            "RETURN file::copy_if_not_exists($s, $t)", {"s": source, "t": target}
        )

    async def rename(self, file: File, key: str) -> None:
        """Move ``file`` to ``key`` within the same bucket."""
        _check_file(file)
        _check_key(key)
        await self._first("RETURN file::rename($f, $k)", {"f": file, "k": key})

    async def rename_if_not_exists(self, file: File, key: str) -> None:
        _check_file(file)
        _check_key(key)
        await self._first(
            "RETURN file::rename_if_not_exists($f, $k)", {"f": file, "k": key}
        )
