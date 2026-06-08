from __future__ import annotations

from collections.abc import Mapping, Sequence

ScopeArg = str | Mapping[str, str] | Sequence[str] | Sequence[tuple[str, str]] | None


def scope_paths(scope: ScopeArg) -> list[str]:
    """Normalise a scope argument to the wire `ScopeSet` (a list of `key=value`
    path strings).

    Accepts a single path string, a mapping, a sequence of path strings, or a
    sequence of `(key, value)` tuples. All forms collapse to `key=value`
    strings; ready-made path strings (including nested `team=acme/project=x`)
    pass through untouched.
    """
    if scope is None:
        return []
    if isinstance(scope, str):
        return [scope]
    if isinstance(scope, Mapping):
        return [f"{k}={v}" for k, v in scope.items()]
    paths: list[str] = []
    for item in scope:
        if isinstance(item, str):
            paths.append(item)
        else:
            key, value = item
            paths.append(f"{key}={value}")
    return paths


__all__ = ["ScopeArg", "scope_paths"]
