"""Every public annotation can be resolved at runtime.

``AsyncSurrealConnection`` and ``BlockingSurrealConnection`` are exported for
exactly one purpose - annotating a connection, because the ``Surreal`` /
``AsyncSurreal`` names are factory functions and cannot be used that way. They
were built as ``Union[..., "AsyncEmbeddedSurrealConnection"]``, and that string
member becomes a ``ForwardRef`` resolved only when something asks for the
annotation at runtime - in the *caller's* namespace, never in ``surrealdb``'s.
So following the SDK's own advice was enough to break a program:

    from surrealdb import BlockingSurrealConnection

    def handler(db: BlockingSurrealConnection) -> None: ...
    typing.get_type_hints(handler)
    # NameError: name 'BlockingEmbeddedSurrealConnection' is not defined

That covers ``typing.get_type_hints``, ``inspect.signature(..., eval_str=True)``,
pydantic's ``validate_call`` and models, and every framework built on them -
FastAPI dependency injection among them. The failure named a class the user had
never mentioned, from a module they had never imported, and it happened whether
or not the embedded extra was installed.

Static typing was fine throughout, which is why nothing caught it: the defect
only exists at runtime.
"""

import inspect
import typing

import pytest

import surrealdb
from surrealdb import AsyncSurrealConnection, BlockingSurrealConnection


def test_the_connection_aliases_resolve() -> None:
    """The documented way to annotate a connection has to actually work."""

    def blocking_handler(db: BlockingSurrealConnection) -> None: ...

    async def async_handler(db: AsyncSurrealConnection) -> None: ...

    assert typing.get_type_hints(blocking_handler)["db"] is BlockingSurrealConnection
    assert typing.get_type_hints(async_handler)["db"] is AsyncSurrealConnection


def test_the_factories_resolve() -> None:
    """``Surreal`` / ``AsyncSurreal`` carry the same union as their return type."""
    assert typing.get_type_hints(surrealdb.Surreal)["return"] is not None
    assert typing.get_type_hints(surrealdb.AsyncSurreal)["return"] is not None


def test_signature_evaluation_works() -> None:
    """``inspect.signature(..., eval_str=True)`` is the other common reader."""

    def handler(db: BlockingSurrealConnection) -> None: ...

    signature = inspect.signature(handler, eval_str=True)
    assert signature.parameters["db"].annotation is BlockingSurrealConnection


def test_no_alias_member_is_an_unresolved_forward_reference() -> None:
    """The root cause, asserted directly.

    A ``ForwardRef`` here is what made every reader above fail, and it would
    come back the moment someone adds a member as a string.
    """
    for alias in (BlockingSurrealConnection, AsyncSurrealConnection):
        for member in typing.get_args(alias):
            assert not isinstance(member, typing.ForwardRef), (
                f"{member!r} is an unresolved forward reference; build the "
                "union from the class itself"
            )
            assert isinstance(member, type), f"{member!r} is not a class"


def test_the_aliases_describe_what_this_install_can_return() -> None:
    """The union members match the engines actually available here."""
    embedded_available = surrealdb._EMBEDDED_AVAILABLE  # pyright: ignore[reportPrivateUsage]
    expected = 3 if embedded_available else 2

    assert len(typing.get_args(BlockingSurrealConnection)) == expected
    assert len(typing.get_args(AsyncSurrealConnection)) == expected


def test_every_public_name_has_resolvable_annotations() -> None:
    """Nothing else in ``__all__`` carries an annotation that cannot be read.

    A sweep rather than a list, so a new export with the same problem is caught
    without anyone remembering to add it here.
    """
    unresolvable: list[str] = []

    for name in surrealdb.__all__:
        obj = getattr(surrealdb, name, None)
        if obj is None:
            continue
        for target in _annotation_carriers(obj):
            try:
                typing.get_type_hints(target)
            except NameError as error:
                unresolvable.append(f"{name}: {error}")
            except Exception:
                # Anything else (C extensions, exotic descriptors) is not what
                # this test is about.
                continue

    assert not unresolvable, "unresolvable annotations: " + "; ".join(unresolvable)


def _annotation_carriers(obj: object) -> list[object]:
    """The parts of *obj* whose annotations ``get_type_hints`` can read.

    Only classes and functions - what ``typing.get_type_hints`` documents as
    valid input. A module-level *instance* such as the ``Null`` sentinel is not:
    it inherits ``__annotations__`` from its class without the module namespace
    that resolves them, so passing one raises ``NameError`` about the SDK's own
    perfectly-resolvable types. That is a property of ``get_type_hints``, not a
    defect in the annotations, and including instances here reported it as one.
    """
    if isinstance(obj, type):
        return [
            obj,
            *(
                member
                for name, member in vars(obj).items()
                if not name.startswith("_") and inspect.isfunction(member)
            ),
        ]
    if inspect.isfunction(obj):
        return [obj]
    return []


@pytest.mark.parametrize(
    "alias", [BlockingSurrealConnection, AsyncSurrealConnection], ids=["sync", "async"]
)
def test_an_alias_can_be_used_in_an_isinstance_check(alias: object) -> None:
    """A union of real classes supports the runtime checks people write."""
    assert isinstance(typing.get_args(alias), tuple)
    # `isinstance` against the union's members is the practical use.
    assert not isinstance(object(), typing.get_args(alias))
