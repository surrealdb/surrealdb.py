from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types.geometry import (
    GeometryCollection,
    GeometryLine,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryPoint,
    GeometryPolygon,
)


# Unit tests for encoding - GeometryPoint
def test_geometry_point_encode() -> None:
    """Test encoding GeometryPoint to CBOR bytes."""
    point = GeometryPoint(1.23, 4.56)
    encoded = cbor.encode(point)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


# Unit tests for decoding - GeometryPoint
def test_geometry_point_decode() -> None:
    """Test decoding CBOR bytes to GeometryPoint."""
    point = GeometryPoint(1.23, 4.56)
    encoded = cbor.encode(point)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, GeometryPoint)
    assert decoded == point


# Encode+decode roundtrip tests - GeometryPoint
def test_geometry_point_roundtrip() -> None:
    """Test encode+decode roundtrip for GeometryPoint."""
    test_points = [
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.23, 4.56),
        GeometryPoint(-7.9735981, 37.0497115),
        GeometryPoint(180.0, 90.0),
        GeometryPoint(-180.0, -90.0),
    ]

    for point in test_points:
        encoded = cbor.encode(point)
        decoded = cbor.decode(encoded)
        assert decoded == point
        assert isinstance(decoded, GeometryPoint)


# Unit tests for encoding - GeometryLine
def test_geometry_line_encode() -> None:
    """Test encoding GeometryLine to CBOR bytes."""
    line = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    encoded = cbor.encode(line)
    assert isinstance(encoded, bytes)


# Unit tests for decoding - GeometryLine
def test_geometry_line_decode() -> None:
    """Test decoding CBOR bytes to GeometryLine."""
    line = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    encoded = cbor.encode(line)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, GeometryLine)
    assert decoded == line


# Encode+decode roundtrip tests - GeometryLine
def test_geometry_line_roundtrip() -> None:
    """Test encode+decode roundtrip for GeometryLine."""
    test_lines = [
        GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0)),
        GeometryLine(
            GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0), GeometryPoint(2.0, 2.0)
        ),
    ]

    for line in test_lines:
        encoded = cbor.encode(line)
        decoded = cbor.decode(encoded)
        assert decoded == line
        assert isinstance(decoded, GeometryLine)


# Unit tests for encoding - GeometryPolygon
def test_geometry_polygon_encode() -> None:
    """Test encoding GeometryPolygon to CBOR bytes."""
    # Create a valid closed ring (triangle)
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.0, 0.0),
        GeometryPoint(1.0, 1.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    polygon = GeometryPolygon(exterior)
    encoded = cbor.encode(polygon)
    assert isinstance(encoded, bytes)


# Unit tests for decoding - GeometryPolygon
def test_geometry_polygon_decode() -> None:
    """Test decoding CBOR bytes to GeometryPolygon."""
    # Create a valid closed ring (triangle)
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.0, 0.0),
        GeometryPoint(1.0, 1.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    polygon = GeometryPolygon(exterior)
    encoded = cbor.encode(polygon)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, GeometryPolygon)
    assert decoded == polygon


# Encode+decode roundtrip tests - GeometryPolygon
def test_geometry_polygon_roundtrip() -> None:
    """Test encode+decode roundtrip for GeometryPolygon."""
    # Create a valid closed ring (square)
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(2.0, 0.0),
        GeometryPoint(2.0, 2.0),
        GeometryPoint(0.0, 2.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    polygon = GeometryPolygon(exterior)
    encoded = cbor.encode(polygon)
    decoded = cbor.decode(encoded)
    assert decoded == polygon
    assert isinstance(decoded, GeometryPolygon)


# Unit tests for encoding - GeometryMultiPoint
def test_geometry_multipoint_encode() -> None:
    """Test encoding GeometryMultiPoint to CBOR bytes."""
    mp = GeometryMultiPoint(GeometryPoint(1.0, 2.0), GeometryPoint(3.0, 4.0))
    encoded = cbor.encode(mp)
    assert isinstance(encoded, bytes)


# Unit tests for decoding - GeometryMultiPoint
def test_geometry_multipoint_decode() -> None:
    """Test decoding CBOR bytes to GeometryMultiPoint."""
    mp = GeometryMultiPoint(GeometryPoint(1.0, 2.0), GeometryPoint(3.0, 4.0))
    encoded = cbor.encode(mp)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, GeometryMultiPoint)
    assert decoded == mp


# Encode+decode roundtrip tests - GeometryMultiPoint
def test_geometry_multipoint_roundtrip() -> None:
    """Test encode+decode roundtrip for GeometryMultiPoint."""
    mp = GeometryMultiPoint(
        GeometryPoint(1.0, 2.0), GeometryPoint(3.0, 4.0), GeometryPoint(5.0, 6.0)
    )
    encoded = cbor.encode(mp)
    decoded = cbor.decode(encoded)
    assert decoded == mp
    assert isinstance(decoded, GeometryMultiPoint)


# Unit tests for encoding - GeometryMultiLine
def test_geometry_multiline_encode() -> None:
    """Test encoding GeometryMultiLine to CBOR bytes."""
    ml = GeometryMultiLine(
        GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0)),
        GeometryLine(GeometryPoint(2.0, 2.0), GeometryPoint(3.0, 3.0)),
    )
    encoded = cbor.encode(ml)
    assert isinstance(encoded, bytes)


# Unit tests for decoding - GeometryMultiLine
def test_geometry_multiline_decode() -> None:
    """Test decoding CBOR bytes to GeometryMultiLine."""
    ml = GeometryMultiLine(
        GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0)),
        GeometryLine(GeometryPoint(2.0, 2.0), GeometryPoint(3.0, 3.0)),
    )
    encoded = cbor.encode(ml)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, GeometryMultiLine)
    assert decoded == ml


# Encode+decode roundtrip tests - GeometryMultiLine
def test_geometry_multiline_roundtrip() -> None:
    """Test encode+decode roundtrip for GeometryMultiLine."""
    ml = GeometryMultiLine(
        GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0)),
        GeometryLine(GeometryPoint(2.0, 2.0), GeometryPoint(3.0, 3.0)),
    )
    encoded = cbor.encode(ml)
    decoded = cbor.decode(encoded)
    assert decoded == ml
    assert isinstance(decoded, GeometryMultiLine)


# Unit tests for encoding - GeometryMultiPolygon
def test_geometry_multipolygon_encode() -> None:
    """Test encoding GeometryMultiPolygon to CBOR bytes."""
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.0, 0.0),
        GeometryPoint(1.0, 1.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    mp = GeometryMultiPolygon(GeometryPolygon(exterior))
    encoded = cbor.encode(mp)
    assert isinstance(encoded, bytes)


# Unit tests for decoding - GeometryMultiPolygon
def test_geometry_multipolygon_decode() -> None:
    """Test decoding CBOR bytes to GeometryMultiPolygon."""
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.0, 0.0),
        GeometryPoint(1.0, 1.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    mp = GeometryMultiPolygon(GeometryPolygon(exterior))
    encoded = cbor.encode(mp)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, GeometryMultiPolygon)
    assert decoded == mp


# Encode+decode roundtrip tests - GeometryMultiPolygon
def test_geometry_multipolygon_roundtrip() -> None:
    """Test encode+decode roundtrip for GeometryMultiPolygon."""
    exterior1 = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.0, 0.0),
        GeometryPoint(1.0, 1.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    exterior2 = GeometryLine(
        GeometryPoint(5.0, 5.0),
        GeometryPoint(6.0, 5.0),
        GeometryPoint(6.0, 6.0),
        GeometryPoint(5.0, 5.0),  # Close the ring
    )
    mp = GeometryMultiPolygon(
        GeometryPolygon(exterior1),
        GeometryPolygon(exterior2),
    )
    encoded = cbor.encode(mp)
    decoded = cbor.decode(encoded)
    assert decoded == mp
    assert isinstance(decoded, GeometryMultiPolygon)


# Unit tests for encoding - GeometryCollection
def test_geometry_collection_encode() -> None:
    """Test encoding GeometryCollection to CBOR bytes."""
    gc = GeometryCollection(
        GeometryPoint(1.1, 2.2),
        GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0)),
    )
    encoded = cbor.encode(gc)
    assert isinstance(encoded, bytes)


# Unit tests for decoding - GeometryCollection
def test_geometry_collection_decode() -> None:
    """Test decoding CBOR bytes to GeometryCollection."""
    gc = GeometryCollection(
        GeometryPoint(1.1, 2.2),
        GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0)),
    )
    encoded = cbor.encode(gc)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, GeometryCollection)
    assert decoded == gc


# Encode+decode roundtrip tests - GeometryCollection
def test_geometry_collection_roundtrip() -> None:
    """Test encode+decode roundtrip for GeometryCollection."""
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.0, 0.0),
        GeometryPoint(1.0, 1.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    gc = GeometryCollection(
        GeometryPoint(1.1, 2.2),
        GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0)),
        GeometryPolygon(exterior),
    )
    encoded = cbor.encode(gc)
    decoded = cbor.decode(encoded)
    assert decoded == gc
    assert isinstance(decoded, GeometryCollection)


@pytest.fixture
async def surrealdb_connection():  # type: ignore[misc]
    url = "ws://localhost:8000/rpc"
    password = "root"
    username = "root"
    vars_params = {"username": username, "password": password}
    database_name = "test_db"
    namespace = "test_ns"
    connection = AsyncWsSurrealConnection(url)
    await connection.signin(vars_params)
    await connection.use(namespace=namespace, database=database_name)
    await connection.query("DELETE geometry_tests;")
    yield connection
    await connection.query("DELETE geometry_tests;")
    await connection.close()


# GeometryPoint tests
@pytest.mark.asyncio
async def test_geometry_point_class_methods() -> None:
    p = GeometryPoint(longitude=1.23, latitude=4.56)
    assert p.get_coordinates() == (1.23, 4.56)
    coords = (10.0, -20.0)
    p2 = GeometryPoint.parse_coordinates(coords)
    assert p2.longitude == 10.0
    assert p2.latitude == -20.0
    p3 = GeometryPoint(10.0, -20.0)
    assert p2 == p3
    assert not p2 == GeometryPoint(0.0, 0.0)


@pytest.mark.asyncio
async def test_geometry_point_db_insert_and_retrieve(surrealdb_connection: Any) -> None:
    geometry_dict = {"type": "Point", "coordinates": [1.23, 4.56]}
    create_query = """
        CREATE geometry_tests:point1 SET geometry = $geo;
    """
    initial_result = await surrealdb_connection.query(
        create_query, vars={"geo": geometry_dict}
    )
    assert "geometry" in initial_result[0]
    select_result = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo = select_result[0]["geometry"]
    assert stored_geo["type"] == "Point"
    assert stored_geo["coordinates"] == [1.23, 4.56]
    retrieved_point = GeometryPoint.parse_coordinates(tuple(stored_geo["coordinates"]))
    assert retrieved_point == GeometryPoint(1.23, 4.56)


@pytest.mark.asyncio
async def test_geometry_point_db_insert_and_retrieve_as_python_object(
    surrealdb_connection,
):
    my_point = GeometryPoint(1.23, 4.56)
    create_query = """
        CREATE geometry_tests:obj_point1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": my_point})
    results = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo_obj = results[0]["geometry"]
    assert isinstance(stored_geo_obj, GeometryPoint)
    assert stored_geo_obj == my_point


@pytest.mark.asyncio
async def test_geometry_point_mixed_coordinates(surrealdb_connection: Any) -> None:
    bad_coords = [
        [-7.9735981, 37.0497115],
        [-7.9758082, 37.0457381],
        [-7.9756148, 37.0383393],
        [-7.9767212, 37.0314215],
        [-7.954491, 37.0309418],
        [-7.9550154, 37.0423815],
        [-7.964371, 37.0471084],
        [-7.9735981, 37.0497115],
        GeometryPoint(-7.9735981, 37.0497115),
    ]
    geometry_dict = {"type": "Polygon", "coordinates": [bad_coords]}
    create_query = """
        CREATE geometry_tests:issue_5204 SET geometry = $geo;
    """
    results = await surrealdb_connection.query(
        create_query, vars={"geo": geometry_dict}
    )
    stored_geo_obj = results[0]["geometry"]
    assert stored_geo_obj == geometry_dict


# GeometryLine tests
@pytest.mark.asyncio
async def test_geometry_line_class_methods() -> None:
    p1 = GeometryPoint(0.0, 0.0)
    p2 = GeometryPoint(1.0, 1.0)
    line = GeometryLine(p1, p2)
    assert line.get_coordinates() == [(0.0, 0.0), (1.0, 1.0)]
    coords = [(10.0, 10.0), (20.0, 20.0)]
    parsed_line = GeometryLine.parse_coordinates(coords)
    assert parsed_line.get_coordinates() == coords
    line2 = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    assert line == line2
    line3 = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(2.0, 2.0))
    assert not line == line3


@pytest.mark.asyncio
async def test_geometry_line_db_insert_and_retrieve(surrealdb_connection: Any) -> None:
    geometry_dict = {
        "type": "Line",
        "coordinates": [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]],
    }
    create_query = """
        CREATE geometry_tests:line1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": geometry_dict})
    select_result = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo = select_result[0]["geometry"]
    assert stored_geo["type"] == "Line"
    assert stored_geo["coordinates"] == [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]]


@pytest.mark.asyncio
async def test_geometry_line_db_insert_and_retrieve_as_python_object(
    surrealdb_connection,
):
    line = GeometryLine(
        GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0), GeometryPoint(2.0, 2.0)
    )
    create_query = """
        CREATE geometry_tests:obj_line1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": line})
    results = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo_obj = results[0]["geometry"]
    assert isinstance(stored_geo_obj, GeometryLine)
    assert stored_geo_obj == line


# GeometryPolygon tests
@pytest.mark.asyncio
async def test_geometry_polygon_class_methods() -> None:
    # Test with a simple polygon (exterior ring only)
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.0, 0.0),
        GeometryPoint(1.0, 1.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    poly = GeometryPolygon(exterior)
    assert poly.get_coordinates() == [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]]

    # Test with polygon with hole
    hole = GeometryLine(
        GeometryPoint(0.25, 0.25),
        GeometryPoint(0.75, 0.25),
        GeometryPoint(0.75, 0.75),
        GeometryPoint(0.25, 0.25),  # Close the ring
    )
    poly_with_hole = GeometryPolygon(exterior, hole)
    assert poly_with_hole.get_coordinates() == [
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)],
        [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.25)],
    ]

    # Test parse_coordinates
    coords = [[(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 0.0)]]
    parsed_poly = GeometryPolygon.parse_coordinates(coords)
    assert parsed_poly.get_coordinates() == coords
    assert poly != parsed_poly


@pytest.mark.asyncio
async def test_geometry_polygon_db_insert_and_retrieve(
    surrealdb_connection: Any,
) -> None:
    geometry_dict = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [0.0, 0.0]]],
    }
    create_query = """
        CREATE geometry_tests:polygon1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": geometry_dict})
    select_result = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo = select_result[0]["geometry"]
    assert stored_geo["type"] == "Polygon"
    assert stored_geo["coordinates"] == [
        [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [0.0, 0.0]]
    ]


@pytest.mark.asyncio
async def test_geometry_polygon_db_insert_and_retrieve_as_python_object(
    surrealdb_connection: Any,
) -> None:
    """Test inserting a GeometryPolygon Python object and retrieving it from the database."""
    # Create a valid polygon with closed ring
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(4.0, 0.0),
        GeometryPoint(4.0, 4.0),
        GeometryPoint(0.0, 4.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    polygon = GeometryPolygon(exterior)

    create_query = """
        CREATE geometry_tests:obj_polygon1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": polygon})
    results = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo_obj = results[0]["geometry"]

    assert isinstance(stored_geo_obj, GeometryPolygon)
    assert stored_geo_obj == polygon


@pytest.mark.asyncio
async def test_geometry_polygon_with_holes() -> None:
    """Test creating a polygon with interior rings (holes)."""
    # Create exterior ring
    exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(10.0, 0.0),
        GeometryPoint(10.0, 10.0),
        GeometryPoint(0.0, 10.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )

    # Create first hole
    hole1 = GeometryLine(
        GeometryPoint(2.0, 2.0),
        GeometryPoint(4.0, 2.0),
        GeometryPoint(4.0, 4.0),
        GeometryPoint(2.0, 4.0),
        GeometryPoint(2.0, 2.0),  # Close the ring
    )

    # Create second hole
    hole2 = GeometryLine(
        GeometryPoint(6.0, 6.0),
        GeometryPoint(8.0, 6.0),
        GeometryPoint(8.0, 8.0),
        GeometryPoint(6.0, 8.0),
        GeometryPoint(6.0, 6.0),  # Close the ring
    )

    # Create polygon with holes
    polygon_with_holes = GeometryPolygon(exterior, hole1, hole2)

    # Verify it has 3 rings (1 exterior + 2 holes)
    assert len(polygon_with_holes.geometry_lines) == 3
    coords = polygon_with_holes.get_coordinates()
    assert len(coords) == 3
    assert coords[0] == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    assert coords[1] == [(2.0, 2.0), (4.0, 2.0), (4.0, 4.0), (2.0, 4.0), (2.0, 2.0)]
    assert coords[2] == [(6.0, 6.0), (8.0, 6.0), (8.0, 8.0), (6.0, 8.0), (6.0, 6.0)]


@pytest.mark.asyncio
async def test_geometry_polygon_validation() -> None:
    """Test that polygon validation catches invalid rings."""
    # Test 1: Ring not closed (first != last point)
    with pytest.raises(ValueError, match="first point.*must equal last point"):
        unclosed_ring = GeometryLine(
            GeometryPoint(0.0, 0.0),
            GeometryPoint(1.0, 0.0),
            GeometryPoint(1.0, 1.0),
            GeometryPoint(0.0, 1.0),  # NOT closed - missing final point
        )
        GeometryPolygon(unclosed_ring)

    # Test 2: Ring with too few points (< 4)
    with pytest.raises(ValueError, match="must have at least 4 points"):
        invalid_ring = GeometryLine(
            GeometryPoint(0.0, 0.0),
            GeometryPoint(1.0, 1.0),
            GeometryPoint(0.0, 0.0),  # Only 3 points total
        )
        GeometryPolygon(invalid_ring)

    # Test 3: Valid exterior but invalid hole
    valid_exterior = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(10.0, 0.0),
        GeometryPoint(10.0, 10.0),
        GeometryPoint(0.0, 10.0),
        GeometryPoint(0.0, 0.0),
    )

    with pytest.raises(ValueError, match="Invalid interior.*ring"):
        invalid_hole = GeometryLine(
            GeometryPoint(2.0, 2.0),
            GeometryPoint(4.0, 2.0),
            GeometryPoint(2.0, 4.0),  # Only 3 points
        )
        GeometryPolygon(valid_exterior, invalid_hole)


@pytest.mark.asyncio
async def test_real_world_polygon_from_kml() -> None:
    """Test creating a polygon from real-world KML data (based on issue #195)."""
    # Coordinates from the issue (simplified from the KML example)
    # These form a closed polygon representing a geographic area
    coords = [
        (-7.9735981, 37.0497115),
        (-7.9758082, 37.0457381),
        (-7.9756148, 37.0383393),
        (-7.9767212, 37.0314215),
        (-7.954491, 37.0309418),
        (-7.9550154, 37.0423815),
        (-7.964371, 37.0471084),
        (-7.9735981, 37.0497115),  # Closed - first == last
    ]

    # Create geometry points
    points = [GeometryPoint(lon, lat) for lon, lat in coords]

    # Create the closed exterior ring
    exterior = GeometryLine(*points)

    # Create the polygon
    polygon = GeometryPolygon(exterior)

    # Verify it's properly created
    assert len(polygon.geometry_lines) == 1
    polygon_coords = polygon.get_coordinates()[0]
    assert len(polygon_coords) == 8  # 7 unique points + 1 closing point
    assert polygon_coords[0] == polygon_coords[-1]  # Verify closed
    assert polygon_coords[0] == (-7.9735981, 37.0497115)

    # Verify we can also parse it from coordinates
    parsed = GeometryPolygon.parse_coordinates([coords])
    assert parsed == polygon


# GeometryMultiPoint tests
@pytest.mark.asyncio
async def test_geometry_multipoint_class_methods() -> None:
    mp = GeometryMultiPoint(
        GeometryPoint(1.0, 2.0),
        GeometryPoint(3.0, 4.0),
        GeometryPoint(5.0, 6.0),
    )
    assert mp.get_coordinates() == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]
    parsed = GeometryMultiPoint.parse_coordinates([(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)])
    assert mp == parsed


@pytest.mark.asyncio
async def test_geometry_multipoint_db_insert_and_retrieve(
    surrealdb_connection: Any,
) -> None:
    geometry_dict = {
        "type": "MultiPoint",
        "coordinates": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
    }
    create_query = """
        CREATE geometry_tests:multipoint1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": geometry_dict})
    select_result = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo = select_result[0]["geometry"]
    assert stored_geo["type"] == "MultiPoint"
    assert stored_geo["coordinates"] == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]


@pytest.mark.asyncio
async def test_geometry_multipoint_db_insert_and_retrieve_as_python_object(
    surrealdb_connection,
):
    mp = GeometryMultiPoint(
        GeometryPoint(1.0, 2.0),
        GeometryPoint(3.0, 4.0),
        GeometryPoint(5.0, 6.0),
    )
    create_query = """
        CREATE geometry_tests:obj_multipoint1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": mp})
    results = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo_obj = results[0]["geometry"]
    assert isinstance(stored_geo_obj, GeometryMultiPoint)
    assert stored_geo_obj == mp


# GeometryMultiLine tests
@pytest.mark.asyncio
async def test_geometry_multiline_class_methods() -> None:
    l1 = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    l2 = GeometryLine(GeometryPoint(2.0, 2.0), GeometryPoint(3.0, 3.0))
    ml = GeometryMultiLine(l1, l2)
    assert ml.get_coordinates() == [[(0.0, 0.0), (1.0, 1.0)], [(2.0, 2.0), (3.0, 3.0)]]
    coords = [[(0.0, 0.0), (1.0, 1.0)], [(2.0, 2.0), (3.0, 3.0)]]
    parsed = GeometryMultiLine.parse_coordinates(coords)
    assert ml == parsed


@pytest.mark.asyncio
async def test_geometry_multiline_db_insert_and_retrieve(
    surrealdb_connection: Any,
) -> None:
    geometry_dict = {
        "type": "MultiLineString",
        "coordinates": [
            [[0.0, 0.0], [1.0, 1.0]],
            [[2.0, 2.0], [3.0, 3.0]],
        ],
    }
    create_query = """
        CREATE geometry_tests:multiline1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": geometry_dict})
    select_result = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo = select_result[0]["geometry"]
    assert stored_geo["type"] == "MultiLineString"
    assert stored_geo["coordinates"] == [
        [[0.0, 0.0], [1.0, 1.0]],
        [[2.0, 2.0], [3.0, 3.0]],
    ]


@pytest.mark.asyncio
async def test_geometry_multiline_db_insert_and_retrieve_as_python_object(
    surrealdb_connection,
):
    line1 = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    line2 = GeometryLine(GeometryPoint(2.0, 2.0), GeometryPoint(3.0, 3.0))
    ml = GeometryMultiLine(line1, line2)
    create_query = """
        CREATE geometry_tests:obj_multiline1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": ml})
    results = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo_obj = results[0]["geometry"]
    assert isinstance(stored_geo_obj, GeometryMultiLine)
    assert stored_geo_obj == ml


# GeometryMultiPolygon tests
@pytest.mark.asyncio
async def test_geometry_multipolygon_class_methods() -> None:
    # Create two valid polygons with closed rings
    exterior1 = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(1.0, 0.0),
        GeometryPoint(1.0, 1.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    p1 = GeometryPolygon(exterior1)

    exterior2 = GeometryLine(
        GeometryPoint(5.0, 5.0),
        GeometryPoint(6.0, 5.0),
        GeometryPoint(6.0, 6.0),
        GeometryPoint(5.0, 5.0),  # Close the ring
    )
    p2 = GeometryPolygon(exterior2)

    mp = GeometryMultiPolygon(p1, p2)
    assert len(mp.geometry_polygons) == 2

    # Test parse_coordinates
    coords = [
        [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]],
        [[(5.0, 5.0), (6.0, 5.0), (6.0, 6.0), (5.0, 5.0)]],
    ]
    parsed = GeometryMultiPolygon.parse_coordinates(coords)
    assert mp == parsed


@pytest.mark.asyncio
async def test_geometry_multipolygon_db_insert_and_retrieve(
    surrealdb_connection: Any,
) -> None:
    geometry_dict = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0.0, 0.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]],
            [[[5.0, 5.0], [6.0, 6.0], [6.0, 5.0], [5.0, 5.0]]],
        ],
    }
    create_query = """
        CREATE geometry_tests:multipolygon1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": geometry_dict})
    select_result = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo = select_result[0]["geometry"]
    assert stored_geo["type"] == "MultiPolygon"
    assert stored_geo["coordinates"] == [
        [[[0.0, 0.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]],
        [[[5.0, 5.0], [6.0, 6.0], [6.0, 5.0], [5.0, 5.0]]],
    ]


@pytest.mark.asyncio
async def test_geometry_multipolygon_db_insert_and_retrieve_as_python_object(
    surrealdb_connection: Any,
) -> None:
    """Test inserting a GeometryMultiPolygon Python object and retrieving it from the database."""
    # Create first polygon
    exterior1 = GeometryLine(
        GeometryPoint(0.0, 0.0),
        GeometryPoint(3.0, 0.0),
        GeometryPoint(3.0, 3.0),
        GeometryPoint(0.0, 3.0),
        GeometryPoint(0.0, 0.0),  # Close the ring
    )
    poly1 = GeometryPolygon(exterior1)

    # Create second polygon
    exterior2 = GeometryLine(
        GeometryPoint(5.0, 5.0),
        GeometryPoint(8.0, 5.0),
        GeometryPoint(8.0, 8.0),
        GeometryPoint(5.0, 8.0),
        GeometryPoint(5.0, 5.0),  # Close the ring
    )
    poly2 = GeometryPolygon(exterior2)

    # Create multipolygon
    multipolygon = GeometryMultiPolygon(poly1, poly2)

    create_query = """
        CREATE geometry_tests:obj_multipolygon1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": multipolygon})
    results = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo_obj = results[0]["geometry"]

    assert isinstance(stored_geo_obj, GeometryMultiPolygon)
    assert stored_geo_obj == multipolygon
    assert len(stored_geo_obj.geometry_polygons) == 2


# GeometryCollection tests
@pytest.mark.asyncio
async def test_geometry_collection_class_methods() -> None:
    pt = GeometryPoint(1.1, 2.2)
    ln = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    gc = GeometryCollection(pt, ln)
    assert len(gc.geometries) == 2
    assert gc == GeometryCollection(pt, ln)


@pytest.mark.asyncio
async def test_geometry_collection_db_insert_and_retrieve(
    surrealdb_connection: Any,
) -> None:
    geometry_dict = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [1.1, 2.2]},
            {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
        ],
    }
    create_query = """
        CREATE geometry_tests:collection1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": geometry_dict})
    select_result = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo = select_result[0]["geometry"]
    assert stored_geo["type"] == "GeometryCollection"
    assert len(stored_geo["geometries"]) == 2


@pytest.mark.asyncio
async def test_geometry_collection_db_insert_and_retrieve_as_python_object(
    surrealdb_connection,
):
    pt = GeometryPoint(1.1, 2.2)
    ln = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    gc = GeometryCollection(pt, ln)
    create_query = """
        CREATE geometry_tests:obj_collection1 SET geometry = $geo;
    """
    await surrealdb_connection.query(create_query, vars={"geo": gc})
    results = await surrealdb_connection.query("SELECT * FROM geometry_tests;")
    stored_geo_obj = results[0]["geometry"]
    assert isinstance(stored_geo_obj, GeometryCollection)
    assert stored_geo_obj == gc
