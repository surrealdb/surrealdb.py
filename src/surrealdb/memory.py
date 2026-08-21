"""Agent memory, which ships separately as ``surrealdb[memory]``.

The implementation lives in the ``surrealdb-memory`` distribution and imports as
``surrealdb_memory``; this module only forwards to it, so the supported spelling
stays ``from surrealdb.memory import Memory``.

It is a module rather than a package on purpose. Two distributions writing into
one ``surrealdb/memory/`` directory installs without complaint and then breaks
on uninstall: the second package's files are removed, ``__init__.py`` with them,
and what is left imports as an empty namespace package - so
``import surrealdb.memory`` still *succeeds* while exporting nothing. A single
file owned by this distribution has nothing to collide with.
"""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Gives mypy and pyright the real symbols; both resolve types through the
    # forwarding below once this is here - `Memory(...)` is checked, and a
    # misspelled attribute is caught, rather than everything degrading to `Any`.
    #
    # A wildcard is the point: the alternative is restating the addon's ~84
    # public names here, which would put a second copy of its surface in the
    # SDK and make every addition to it a change in both packages. pyright's
    # rule against wildcard-importing a library is aimed at namespace
    # pollution, which is the one thing a forwarding module is *for*.
    from surrealdb_memory import *  # noqa: F403 # pyright: ignore[reportWildcardImportFromLibrary]

# Attribute access raises `ImportError`, not `AttributeError`, when the addon is
# absent. That is deliberate: `AttributeError` here reads as "module
# 'surrealdb.memory' has no attribute 'Memory'", which says nothing about the
# install that would fix it. The cost is that `hasattr()` propagates instead of
# returning False, and `getattr(mod, name, default)` raises instead of falling
# back to its default - both of those swallow `AttributeError` only. With the
# addon installed, a genuinely missing name raises `AttributeError` as usual,
# because the lookup reaches the real module.
_INSTALL_HINT = (
    "the agent memory client, which ships separately.\n"
    "    pip install 'surrealdb[memory]'    # or: uv add 'surrealdb[memory]'"
)


def _addon() -> ModuleType:
    try:
        import surrealdb_memory
    except ModuleNotFoundError as exc:  # pragma: no cover - trivial re-raise
        raise ImportError(f"{__name__} needs {_INSTALL_HINT}") from exc
    return surrealdb_memory


def __getattr__(name: str) -> Any:  # PEP 562
    # `__all__` has to be forwarded for `from surrealdb.memory import *` to see
    # anything. Every other dunder must not be: `from x import y` probes
    # `__path__` first, and answering that turns this module into something the
    # import system treats as a package.
    if name == "__all__":
        return _addon().__all__
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    try:
        return getattr(_addon(), name)
    except ImportError:
        # Name the symbol the caller asked for, not the module.
        raise ImportError(f"{name!r} needs {_INSTALL_HINT}") from None


def __dir__() -> list[str]:
    try:
        return sorted(_addon().__all__)
    except ImportError:
        return []
