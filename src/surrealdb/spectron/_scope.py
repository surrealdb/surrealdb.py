from __future__ import annotations

from collections.abc import Sequence

ScopeClause = str | Sequence[str]
ScopeArg = str | Sequence[ScopeClause] | None


def _clause_paths(clause: ScopeClause) -> list[str]:
    """Normalise a single clause to its ordered, de-duplicated AND-set of
    slash-path strings.

    A string is a single path; a sequence of strings passes through. Empty
    paths are dropped.
    """
    raw = [clause] if isinstance(clause, str) else list(clause)
    out: list[str] = []
    for path in raw:
        if path and path not in out:
            out.append(path)
    return out


def scope_sets(scope: ScopeArg) -> list[list[str]]:
    """Normalise a scope argument to a DNF (disjunctive-normal-form) selector:
    an OR of conjunctive clauses, each clause an AND of slash-path strings.

    The wire shape is `array<array<string>>`. The outer list is an OR across
    clauses, each inner list an AND of scope paths within a clause:

    - A bare string is one singleton clause: `"team/eng"` -> `[["team/eng"]]`.
    - A flat list of strings is an OR of singletons:
      `["a", "b"]` -> `[["a"], ["b"]]`.
    - A nested list is an AND clause: `[["a", "b"]]` -> `[["a", "b"]]`.
    - The two forms mix: `["a", ["b", "c"]]` -> `[["a"], ["b", "c"]]`.

    `None` or empty yields `[]` (the key's default write region). Empty paths
    and empty clauses are dropped, and identical clauses are de-duplicated while
    preserving order.
    """
    if scope is None:
        return []
    clauses: Sequence[ScopeClause] = [scope] if isinstance(scope, str) else scope
    out: list[list[str]] = []
    for clause in clauses:
        paths = _clause_paths(clause)
        if paths and paths not in out:
            out.append(paths)
    return out


__all__ = ["ScopeArg", "scope_sets"]
