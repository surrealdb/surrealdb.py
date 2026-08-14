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


def test_no_exported_union_holds_an_unresolved_forward_reference() -> None:
    """The same rule, applied to every exported union rather than two named ones.

    The sweep below cannot see this: ``get_type_hints`` takes a module, class or
    function, and a ``typing.Union`` object is none of those, so
    ``_annotation_carriers`` returns nothing for one and the union is never
    looked at. ``RecordIdValue`` was exported carrying three ``ForwardRef``s
    that no caller's namespace can resolve, the whole test module here existed
    to prevent exactly that, and every test in it still passed.

    Recursive, because a union can nest one.
    """

    def unresolved(annotation: object, seen: set[int]) -> list[object]:
        if id(annotation) in seen:
            return []
        seen.add(id(annotation))
        found: list[object] = []
        for member in typing.get_args(annotation):
            if isinstance(member, typing.ForwardRef):
                found.append(member)
            else:
                found.extend(unresolved(member, seen))
        return found

    offenders: list[str] = []
    for name in surrealdb.__all__:
        obj = getattr(surrealdb, name, None)
        if obj is None or isinstance(obj, type) or inspect.isfunction(obj):
            continue
        for member in unresolved(obj, set()):
            offenders.append(f"{name}: {member!r}")

    assert not offenders, (
        "exported type aliases holding unresolved forward references "
        "(build them from the real types, not from strings): " + "; ".join(offenders)
    )


def test_every_exported_alias_can_actually_annotate() -> None:
    """The property a caller cares about, exercised the way they would hit it.

    ``get_type_hints`` on a function annotated with the alias is what pydantic,
    FastAPI and ``inspect.signature(..., eval_str=True)`` all end up doing.
    """
    failures: list[str] = []

    for name in surrealdb.__all__:
        obj = getattr(surrealdb, name, None)
        if obj is None or isinstance(obj, type) or inspect.isfunction(obj):
            continue
        if typing.get_args(obj) == ():
            continue  # not a generic alias, nothing to resolve

        namespace: dict[str, object] = {"_alias": obj}
        exec("def _handler(value: _alias) -> None: ...", namespace)  # noqa: S102
        try:
            typing.get_type_hints(namespace["_handler"])
        except Exception as error:  # noqa: BLE001 - reporting, not handling
            failures.append(f"{name}: {type(error).__name__}: {error}")

    assert not failures, "aliases that cannot be used to annotate: " + "; ".join(
        failures
    )


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
