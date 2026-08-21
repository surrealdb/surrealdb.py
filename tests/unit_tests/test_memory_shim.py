"""``surrealdb.memory`` forwards to the separately shipped memory client.

The client used to be vendored here as ``surrealdb.spectron``, bundled into
every install. It now lives in the ``surrealdb-memory`` distribution, pulled by
``surrealdb[memory]``, so it can move across its own major versions while the
SDK stays put. ``surrealdb/memory.py`` is what keeps the import path short.

The two tests about the *core* namespace at the bottom came from the addon's own
suite, which had been importing ``surrealdb`` to assert things about it. The
boundary belongs to the side that owns the shim.
"""

import builtins
import importlib
import sys

import pytest

import surrealdb.memory


def test_it_forwards_to_the_addon() -> None:
    import surrealdb_memory

    assert surrealdb.memory.Memory is surrealdb_memory.Memory
    assert surrealdb.memory.AsyncMemory is surrealdb_memory.AsyncMemory


def test_from_import_works() -> None:
    from surrealdb.memory import AsyncMemory, Memory

    assert Memory.__name__ == "Memory"
    assert AsyncMemory.__name__ == "AsyncMemory"


def test_star_import_sees_the_addons_all() -> None:
    """``__all__`` is the one dunder the shim forwards.

    Without it ``from surrealdb.memory import *`` binds nothing, because the
    shim's own module namespace is almost empty.
    """
    import surrealdb_memory

    assert surrealdb.memory.__all__ == surrealdb_memory.__all__

    namespace: dict[str, object] = {}
    exec("from surrealdb.memory import *", namespace)
    assert "Memory" in namespace
    assert namespace["Memory"] is surrealdb_memory.Memory


def test_it_is_a_module_not_a_package() -> None:
    """A package here would be a directory two distributions both write into.

    That installs quietly and breaks on uninstall: the survivor imports as an
    empty namespace package, so ``import surrealdb.memory`` still succeeds while
    exporting nothing.
    """
    assert not hasattr(surrealdb.memory, "__path__")
    assert surrealdb.memory.__file__ is not None
    assert surrealdb.memory.__file__.endswith("memory.py")


def test_dir_lists_the_addons_surface() -> None:
    assert "Memory" in dir(surrealdb.memory)
    assert "AsyncMemory" in dir(surrealdb.memory)


def test_a_missing_name_still_raises_attribute_error() -> None:
    with pytest.raises(AttributeError):
        surrealdb.memory.NoSuchThing  # noqa: B018


def test_the_error_names_the_symbol_and_the_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the addon absent, the message has to be actionable.

    ``from x import y`` probes ``__path__`` before the symbol, so a shim that
    forwards every dunder reports ``'__path__' needs ...`` instead of naming
    what the caller actually asked for.
    """
    monkeypatch.delitem(sys.modules, "surrealdb_memory", raising=False)
    monkeypatch.delitem(sys.modules, "surrealdb.memory", raising=False)

    real_import = builtins.__import__

    def refuse(name: str, *args: object, **kwargs: object) -> object:
        if name == "surrealdb_memory":
            raise ModuleNotFoundError("No module named 'surrealdb_memory'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", refuse)
    importlib.import_module("surrealdb.memory")

    # `from x import y` is the spelling that exposed this: it probes `__path__`
    # before the symbol, so a shim forwarding every dunder answers with
    # `'__path__' needs ...` and never names what was asked for. Attribute
    # access alone does not go down that path, so it cannot catch the leak.
    with pytest.raises(ImportError) as caught:
        exec("from surrealdb.memory import Memory", {})

    message = str(caught.value)
    assert "'Memory'" in message, "the message must name the symbol, not __path__"
    assert "surrealdb[memory]" in message
    assert "__path__" not in message


def test_importing_the_shim_does_not_need_the_addon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The module itself must import cleanly; only attribute access can fail."""
    monkeypatch.delitem(sys.modules, "surrealdb_memory", raising=False)
    monkeypatch.delitem(sys.modules, "surrealdb.memory", raising=False)

    real_import = builtins.__import__

    def refuse(name: str, *args: object, **kwargs: object) -> object:
        if name == "surrealdb_memory":
            raise ModuleNotFoundError("No module named 'surrealdb_memory'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", refuse)

    assert importlib.import_module("surrealdb.memory") is not None
    assert dir(importlib.import_module("surrealdb.memory")) == []


# --------------------------------------------------------- the core boundary


def test_the_client_is_not_re_exported_at_the_top_level() -> None:
    """``surrealdb.Memory`` must not exist - the path is ``surrealdb.memory``."""
    for name in (
        "Memory",
        "AsyncMemory",
        "MemoryServiceError",
        "MemoryAPIError",
        "MemoryAuthError",
        "MemoryScopeError",
        "MemoryNotFoundError",
    ):
        assert not hasattr(surrealdb, name), f"surrealdb still exposes {name}"
        assert name not in surrealdb.__all__


def test_the_base_error_does_not_shadow_the_builtin() -> None:
    """Why the base error is ``MemoryServiceError`` and not ``MemoryError``."""
    assert not hasattr(surrealdb.memory, "MemoryError")
    assert not issubclass(surrealdb.memory.MemoryServiceError, builtins.MemoryError)


def test_core_does_not_import_the_addon_on_import_surrealdb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain ``import surrealdb`` must not drag the memory client in.

    The forwarding is lazy; if it were not, `surrealdb[memory]` would be
    mandatory in practice whatever the metadata said.
    """
    for mod in [m for m in sys.modules if m.startswith(("surrealdb", "surrealdb_"))]:
        monkeypatch.delitem(sys.modules, mod, raising=False)

    importlib.import_module("surrealdb")

    assert "surrealdb_memory" not in sys.modules
