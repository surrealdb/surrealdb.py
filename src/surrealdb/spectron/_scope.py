from __future__ import annotations

from collections.abc import Mapping


def serialise_scope(scope: Mapping[str, str] | None) -> list[dict[str, str]] | None:
    if scope is None:
        return None
    return [{"key": str(k), "value": str(v)} for k, v in scope.items()]


def deserialise_scope(wire: list[dict[str, str]] | None) -> dict[str, str]:
    if not wire:
        return {}
    out: dict[str, str] = {}
    for entry in wire:
        if not isinstance(entry, Mapping):
            continue
        key = entry.get("key")
        value = entry.get("value")
        if key is not None and value is not None:
            out[str(key)] = str(value)
    return out


__all__ = ["serialise_scope", "deserialise_scope"]
