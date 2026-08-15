"""Every geometry you can send to the server is reachable from ``surrealdb``.

``surrealdb.__all__`` used to contain exactly one geometry name - ``Geometry``,
the base class - and that is the single one you cannot send anywhere. It
constructs happily and then fails at encode time with "cannot encode Geometry".
The seven usable classes had to be imported from
``surrealdb.data.types.geometry``, which nothing in the README mentions.

This is the same mistake as ``Range`` shipping without ``Bound``, so the guard
here is the general one rather than a list of the names that were missing: if
the encoder accepts a type, the package has to export it. ``test_init_functions``
already checks the other direction (every name in ``__all__`` exists), and the
pair of them is what closes the hole.

``GeometryCollection`` is deliberately included even though it is *not* a
``Geometry`` subclass - it is a standalone class that holds them. Walking
``Geometry.__subclasses__()`` would silently skip it, which is precisely how it
would go unexported again.
"""

import inspect
from typing import Any

import pytest

import surrealdb
from surrealdb.data import cbor
from surrealdb.data.types import geometry
from surrealdb.data.types.geometry import (
    Geometry,
    GeometryCollection,
    GeometryLine,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryPoint,
    GeometryPolygon,
)

_POINT = GeometryPoint(1.0, 2.0)
_LINE = GeometryLine(_POINT, GeometryPoint(3.0, 4.0))
# A polygon ring is validated: at least four points, closing on the first.
_RING = GeometryLine(
    GeometryPoint(0.0, 0.0),
    GeometryPoint(1.0, 0.0),
    GeometryPoint(1.0, 1.0),
    GeometryPoint(0.0, 0.0),
)
_POLYGON = GeometryPolygon(_RING)

# One constructed value per public geometry class. A new class with no entry
# fails `test_every_public_geometry_class_has_a_sample` rather than quietly
# dropping out of the coverage below.
SAMPLES: dict[str, Any] = {
    "GeometryPoint": _POINT,
    "GeometryLine": _LINE,
    "GeometryPolygon": _POLYGON,
    "GeometryMultiPoint": GeometryMultiPoint(_POINT),
    "GeometryMultiLine": GeometryMultiLine(_LINE),
    "GeometryMultiPolygon": GeometryMultiPolygon(_POLYGON),
    "GeometryCollection": GeometryCollection(_POINT),
}


def _public_geometry_classes() -> dict[str, type]:
    """Every public class defined in the geometry module, base included."""
    return {
        name: obj
        for name, obj in inspect.getmembers(geometry, inspect.isclass)
        if not name.startswith("_") and obj.__module__ == geometry.__name__
    }


def test_every_public_geometry_class_has_a_sample() -> None:
    """Keeps the table above honest when a class is added."""
    covered = set(SAMPLES) | {"Geometry"}

    assert set(_public_geometry_classes()) == covered


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_a_usable_geometry_is_exported_from_the_package(name: str) -> None:
    assert name in surrealdb.__all__, (
        f"{name} encodes and round-trips, but is not in surrealdb.__all__, "
        f"so it can only be reached via surrealdb.data.types.geometry"
    )
    assert getattr(surrealdb, name) is _public_geometry_classes()[name]


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_the_exported_class_is_the_one_that_encodes(name: str) -> None:
    """The export is only worth anything if that exact class round-trips."""
    sample = SAMPLES[name]

    decoded = cbor.decode(cbor.encode(sample))

    assert decoded == sample
    assert isinstance(decoded, getattr(surrealdb, name))


def test_the_base_class_is_exported_but_cannot_be_sent() -> None:
    """Why ``Geometry`` stays exported: it is for ``isinstance`` and annotations.

    It is kept deliberately, not by the oversight that left it there alone. The
    refusal is asserted so that "the base class does not encode" stays a fact
    rather than an assumption this module is built on.
    """
    assert "Geometry" in surrealdb.__all__

    with pytest.raises(TypeError, match="cannot encode"):
        cbor.encode(Geometry())


def test_isinstance_against_the_exported_base_still_works() -> None:
    """The one thing the base export is actually for."""
    assert isinstance(_POINT, surrealdb.Geometry)

    # Documented oddity: a collection holds geometries but is not one, so a
    # `Geometry` annotation will not accept it. Widening that is additive and
    # can happen later; asserting it here stops the surprise being silent.
    assert not isinstance(SAMPLES["GeometryCollection"], surrealdb.Geometry)
