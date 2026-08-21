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
import importlib.util
import pathlib
import re
import sys

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

import surrealdb.memory

# The addon is an extra, so the SDK's own suite has to pass without it - the
# `floors` job resolves `[project.dependencies]` only, and that is exactly the
# environment a user who never asked for `[memory]` is in. Tests that need the
# real client say so; the ones that cover its *absence* patch the import and run
# everywhere.
HAS_ADDON = importlib.util.find_spec("surrealdb_memory") is not None

needs_addon = pytest.mark.skipif(
    not HAS_ADDON, reason="surrealdb[memory] is not installed in this environment"
)


def _without_the_addon(monkeypatch: pytest.MonkeyPatch) -> object:
    """Reimport the shim with `surrealdb_memory` unimportable."""
    monkeypatch.delitem(sys.modules, "surrealdb_memory", raising=False)
    monkeypatch.delitem(sys.modules, "surrealdb.memory", raising=False)
    real_import = builtins.__import__

    def refuse(name: str, *args: object, **kwargs: object) -> object:
        if name == "surrealdb_memory":
            raise ModuleNotFoundError("No module named 'surrealdb_memory'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", refuse)
    return importlib.import_module("surrealdb.memory")


@needs_addon
def test_it_forwards_to_the_addon() -> None:
    import surrealdb_memory

    assert surrealdb.memory.Memory is surrealdb_memory.Memory
    assert surrealdb.memory.AsyncMemory is surrealdb_memory.AsyncMemory


@needs_addon
def test_from_import_works() -> None:
    from surrealdb.memory import AsyncMemory, Memory

    assert Memory.__name__ == "Memory"
    assert AsyncMemory.__name__ == "AsyncMemory"


@needs_addon
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


@needs_addon
def test_dir_lists_the_addons_surface() -> None:
    assert "Memory" in dir(surrealdb.memory)
    assert "AsyncMemory" in dir(surrealdb.memory)


@needs_addon
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
    _without_the_addon(monkeypatch)

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
    shim = _without_the_addon(monkeypatch)

    assert shim is not None
    assert dir(shim) == []


def test_hasattr_propagates_when_the_addon_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A documented consequence of raising ``ImportError`` over ``AttributeError``.

    ``hasattr`` and the three-argument ``getattr`` swallow ``AttributeError``
    only, so with the addon missing they raise rather than reporting ``False`` or
    falling back to a default. That is the accepted cost of an error that names
    the install instead of saying the attribute does not exist - recorded here so
    it stays a decision rather than becoming a surprise.
    """
    shim = _without_the_addon(monkeypatch)

    with pytest.raises(ImportError):
        hasattr(shim, "Memory")

    with pytest.raises(ImportError):
        getattr(shim, "Memory", "fallback")

    # Dunders are still ordinary attribute lookups, so this one stays False.
    assert not hasattr(shim, "__path__")


# --------------------------------------------------------- the extra's pin

_REPO = pathlib.Path(__file__).resolve().parents[2]


def _declared_addon_version() -> str:
    text = (_REPO / "memory" / "pyproject.toml").read_text()
    found = re.findall(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert len(found) == 1, (
        f"expected one version in memory/pyproject.toml, got {found}"
    )
    return found[0]


def _declared_pin() -> str:
    text = (_REPO / "pyproject.toml").read_text()
    found = re.findall(r'"(surrealdb-memory[^"]*)"', text)
    assert len(found) == 1, f"expected one memory pin in pyproject.toml, got {found}"
    return found[0]


def test_the_declared_pin_admits_the_declared_version() -> None:
    """Source-level twin of the metadata check below, and the sharper of the two.

    The metadata version only bites once the environment has been re-synced: an
    editable install caches ``Requires-Dist`` at install time, so editing the pin
    and running the suite passes against stale metadata. This reads both
    pyproject files, so it fails the moment the two disagree.

    The failure it exists for is silent. ``>=1.0`` does not admit ``1.0.0b1`` - a
    specifier that does not itself name a pre-release excludes them - so relaxing
    the floor while the client is on its beta line leaves ``surrealdb[memory]``
    resolving to nothing. The dev environment never notices, because it installs
    the addon from a path dependency and never consults the floor at all.
    """
    if not (_REPO / "memory" / "pyproject.toml").is_file():  # pragma: no cover
        pytest.skip("memory/pyproject.toml is only present in a checkout")

    shipped = Version(_declared_addon_version())
    pin = Requirement(_declared_pin())

    assert pin.specifier.contains(shipped), (
        f"the [memory] extra declares {pin.specifier}, which does not admit the "
        f"version memory/pyproject.toml declares ({shipped}) - "
        f"`surrealdb[memory]` would resolve to nothing"
    )


@needs_addon
def test_the_extra_admits_the_version_the_addon_ships() -> None:
    """The ``[memory]`` floor has to admit the version actually published.

    ``>=1.0`` does *not* admit ``1.0.0b1``: a specifier that does not itself name
    a pre-release excludes them. So tidying the floor to ``>=1.0`` while the
    client is on its beta line would leave ``surrealdb[memory]`` resolving to
    nothing - an install-time failure for users that nothing in this repo would
    otherwise catch, because the dev environment uses a path dependency and never
    consults the floor at all.

    Asserted against installed metadata rather than the source, so it is checking
    what a wheel would actually carry. ``contains`` is called without
    ``prereleases=True`` deliberately - passing it would mask exactly this bug.
    """
    import importlib.metadata as md

    shipped = Version(md.version("surrealdb-memory"))
    pins = [
        Requirement(r)
        for r in (md.requires("surrealdb") or [])
        if Requirement(r).name == "surrealdb-memory"
    ]

    assert len(pins) == 1, f"expected one memory pin, found {[str(p) for p in pins]}"
    pin = pins[0]

    assert pin.specifier.contains(shipped), (
        f"the [memory] extra pins {pin.specifier} which does not admit the "
        f"version the addon ships ({shipped}); `surrealdb[memory]` would not resolve"
    )


def test_the_declared_pin_is_a_floor_not_an_exact_match() -> None:
    """An ``==`` pin would re-weld the release cadences the split separated.

    ``embedded`` pins exactly on purpose - that extension is compiled against the
    SDK and has to match it. This client speaks HTTP to a separate service, so an
    exact pin would mean a memory release could not ship without an SDK release,
    which is the one thing shipping it separately was meant to avoid.

    Read from the source rather than installed metadata for the same reason as
    the test above: metadata is captured at install time, so an `==` introduced
    since the last sync would pass unnoticed.
    """
    if not (_REPO / "memory" / "pyproject.toml").is_file():  # pragma: no cover
        pytest.skip("only meaningful in a checkout")

    pin = Requirement(_declared_pin())
    operators = {spec.operator for spec in pin.specifier}

    assert operators == {">="}, (
        f"the [memory] extra declares {pin.specifier}; it has to be a `>=` floor "
        f"so the addon can move without an SDK release"
    )


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


@needs_addon
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
