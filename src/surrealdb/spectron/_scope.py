from __future__ import annotations

from collections.abc import Mapping, Sequence

ScopeArg = str | Mapping[str, str] | Sequence[str] | Sequence[tuple[str, str]] | None


def scope_paths(scope: ScopeArg) -> list[str]:
    """Normalise a scope argument to an ordered, de-duplicated list of
    slash-path strings, e.g. `["team/eng"]`.

    A mapping or `(key, value)` tuple becomes a `key/value` path; path strings
    pass through. `None` or empty yields `[]` (the key's default write region).
    """
    if scope is None:
        return []
    if isinstance(scope, str):
        raw: list[str] = [scope]
    elif isinstance(scope, Mapping):
        raw = [f"{k}/{v}" for k, v in scope.items()]
    else:
        raw = []
        for item in scope:
            if isinstance(item, str):
                raw.append(item)
            else:
                key, value = item
                raw.append(f"{key}/{value}")
    out: list[str] = []
    for path in raw:
        if path and path not in out:
            out.append(path)
    return out


__all__ = ["ScopeArg", "scope_paths"]
