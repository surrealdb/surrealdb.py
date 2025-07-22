import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.geometry import (
    GeometryCollection,
    GeometryLine,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryPoint,
    GeometryPolygon,
)


@pytest.fixture
async def surrealdb_connection():
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
async def test_geometry_point_class_methods():
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
async def test_geometry_point_db_insert_and_retrieve(surrealdb_connection):
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
async def test_geometry_point_mixed_coordinates(surrealdb_connection):
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
async def test_geometry_line_class_methods():
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
async def test_geometry_line_db_insert_and_retrieve(surrealdb_connection):
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
async def test_geometry_polygon_class_methods():
    line1 = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    line2 = GeometryLine(GeometryPoint(1.0, 1.0), GeometryPoint(2.0, 2.0))
    poly = GeometryPolygon(line1, line2)
    assert poly.get_coordinates() == [
        [(0.0, 0.0), (1.0, 1.0)],
        [(1.0, 1.0), (2.0, 2.0)],
    ]
    coords = [
        [(0.0, 0.0), (1.0, 1.0)],
        [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
    ]
    parsed_poly = GeometryPolygon.parse_coordinates(coords)
    assert parsed_poly.get_coordinates() == coords
    assert poly != parsed_poly


@pytest.mark.asyncio
async def test_geometry_polygon_db_insert_and_retrieve(surrealdb_connection):
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


# GeometryMultiPoint tests
@pytest.mark.asyncio
async def test_geometry_multipoint_class_methods():
    mp = GeometryMultiPoint(
        GeometryPoint(1.0, 2.0),
        GeometryPoint(3.0, 4.0),
        GeometryPoint(5.0, 6.0),
    )
    assert mp.get_coordinates() == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]
    parsed = GeometryMultiPoint.parse_coordinates([(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)])
    assert mp == parsed


@pytest.mark.asyncio
async def test_geometry_multipoint_db_insert_and_retrieve(surrealdb_connection):
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
async def test_geometry_multiline_class_methods():
    l1 = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    l2 = GeometryLine(GeometryPoint(2.0, 2.0), GeometryPoint(3.0, 3.0))
    ml = GeometryMultiLine(l1, l2)
    assert ml.get_coordinates() == [[(0.0, 0.0), (1.0, 1.0)], [(2.0, 2.0), (3.0, 3.0)]]
    coords = [[(0.0, 0.0), (1.0, 1.0)], [(2.0, 2.0), (3.0, 3.0)]]
    parsed = GeometryMultiLine.parse_coordinates(coords)
    assert ml == parsed


@pytest.mark.asyncio
async def test_geometry_multiline_db_insert_and_retrieve(surrealdb_connection):
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
async def test_geometry_multipolygon_class_methods():
    p1 = GeometryPolygon(
        GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0)),
        GeometryLine(GeometryPoint(1.0, 1.0), GeometryPoint(0.0, 2.0)),
    )
    p2 = GeometryPolygon(
        GeometryLine(GeometryPoint(5.0, 5.0), GeometryPoint(6.0, 6.0)),
        GeometryLine(GeometryPoint(6.0, 6.0), GeometryPoint(5.0, 7.0)),
    )
    mp = GeometryMultiPolygon(p1, p2)
    assert len(mp.geometry_polygons) == 2
    coords = [
        [[(0.0, 0.0), (1.0, 1.0)], [(1.0, 1.0), (0.0, 2.0)]],
        [[(5.0, 5.0), (6.0, 6.0)], [(6.0, 6.0), (5.0, 7.0)]],
    ]
    parsed = GeometryMultiPolygon.parse_coordinates(coords)
    assert mp == parsed


@pytest.mark.asyncio
async def test_geometry_multipolygon_db_insert_and_retrieve(surrealdb_connection):
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


# GeometryCollection tests
@pytest.mark.asyncio
async def test_geometry_collection_class_methods():
    pt = GeometryPoint(1.1, 2.2)
    ln = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
    gc = GeometryCollection(pt, ln)
    assert len(gc.geometries) == 2
    assert gc == GeometryCollection(pt, ln)


@pytest.mark.asyncio
async def test_geometry_collection_db_insert_and_retrieve(surrealdb_connection):
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
