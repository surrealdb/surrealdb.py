import unittest
from unittest import IsolatedAsyncioTestCase

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.geometry import (
    GeometryPoint,
    GeometryLine,
    GeometryPolygon,
    GeometryMultiPoint,
    GeometryMultiLine,
    GeometryMultiPolygon,
    GeometryCollection,
)


class BaseTestGeometry(IsolatedAsyncioTestCase):
    """
    Base class that sets up a SurrealDB connection (async), signs in,
    and does general cleanup. All geometry test classes inherit from this.
    """

    async def asyncSetUp(self):
        self.url = "ws://localhost:8000/rpc"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.connection = AsyncWsSurrealConnection(self.url)

        await self.connection.signin(self.vars_params)
        await self.connection.use(namespace=self.namespace, database=self.database_name)

        await self.connection.query("DELETE geometry_tests;")

    async def asyncTearDown(self):
        await self.connection.query("DELETE geometry_tests;")
        await self.connection.close()


class TestGeometryPoint(BaseTestGeometry):
    """
    Tests for the GeometryPoint class:
    - Class methods: get_coordinates, parse_coordinates, __eq__, etc.
    - DB insert/retrieve for a Point geometry.
    """

    async def test_class_methods(self):
        # Test get_coordinates
        p = GeometryPoint(longitude=1.23, latitude=4.56)
        self.assertEqual(p.get_coordinates(), (1.23, 4.56))

        # Test parse_coordinates
        coords = (10.0, -20.0)
        p2 = GeometryPoint.parse_coordinates(coords)
        self.assertEqual(p2.longitude, 10.0)
        self.assertEqual(p2.latitude, -20.0)

        # Test equality
        p3 = GeometryPoint(10.0, -20.0)
        self.assertTrue(p2 == p3)
        self.assertFalse(p2 == GeometryPoint(0.0, 0.0))

    async def test_db_insert_and_retrieve_point(self):
        """
        Demonstrates storing a point geometry in SurrealDB, then retrieving it
        and verifying that it matches what was inserted.
        """
        geometry_dict = {
            "type": "Point",
            "coordinates": [1.23, 4.56],
        }

        create_query = """
            CREATE geometry_tests:point1 SET geometry = $geo;
        """
        initial_result = await self.connection.query(
            create_query, params={"geo": geometry_dict}
        )
        self.assertTrue("geometry" in initial_result[0])

        select_result = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo = select_result[0]["geometry"]
        self.assertEqual(stored_geo["type"], "Point")
        self.assertEqual(stored_geo["coordinates"], [1.23, 4.56])

        retrieved_point = GeometryPoint.parse_coordinates(tuple(stored_geo["coordinates"]))
        self.assertEqual(retrieved_point, GeometryPoint(1.23, 4.56))

    async def test_db_insert_and_retrieve_point_as_python_object(self):
        """
        Insert a GeometryPoint object directly into DB via SurrealDB's
        custom CBOR encoding/decoding, then retrieve it and verify it
        comes back as a GeometryPoint instance.
        """
        my_point = GeometryPoint(1.23, 4.56)

        create_query = """
            CREATE geometry_tests:obj_point1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": my_point})

        results = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo_obj = results[0]["geometry"]

        self.assertIsInstance(stored_geo_obj, GeometryPoint)
        self.assertEqual(stored_geo_obj, my_point)

    async def test_mixed_coordinates(self):
        """
        Reproduce the scenario from GitHub issue #5204 by mixing
        numeric coordinate pairs with a GeometryPoint object
        inside a Polygon's 'coordinates' list. This should cause
        'TypeError: GeometryPoint object is not subscriptable'.
        """
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

        geometry_dict = {
            "type": "Polygon",
            "coordinates": [bad_coords],
        }

        create_query = """
            CREATE geometry_tests:issue_5204 SET geometry = $geo;
        """

        results = await self.connection.query(create_query, params={"geo": geometry_dict})
        stored_geo_obj = results[0]["geometry"]
        self.assertEqual(stored_geo_obj, geometry_dict)


class TestGeometryLine(BaseTestGeometry):
    """
    Tests for the GeometryLine class.
    """

    async def test_class_methods(self):
        # Construct a line of points
        p1 = GeometryPoint(0, 0)
        p2 = GeometryPoint(1, 1)
        line = GeometryLine(p1, p2)

        # get_coordinates
        self.assertEqual(line.get_coordinates(), [(0, 0), (1, 1)])

        # parse_coordinates
        coords = [(10, 10), (20, 20)]
        parsed_line = GeometryLine.parse_coordinates(coords)
        self.assertEqual(parsed_line.get_coordinates(), coords)

        # equality
        line2 = GeometryLine(GeometryPoint(0, 0), GeometryPoint(1, 1))
        self.assertTrue(line == line2)
        line3 = GeometryLine(GeometryPoint(0, 0), GeometryPoint(2, 2))
        self.assertFalse(line == line3)

    async def test_db_insert_and_retrieve_line(self):
        geometry_dict = {
            "type": "Line",
            "coordinates": [[0, 0], [1, 1], [2, 2]],
        }
        create_query = """
            CREATE geometry_tests:line1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": geometry_dict})

        select_result = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo = select_result[0]["geometry"]
        self.assertEqual(stored_geo["type"], "Line")
        self.assertEqual(stored_geo["coordinates"], [[0, 0], [1, 1], [2, 2]])

    async def test_db_insert_and_retrieve_line_as_python_object(self):
        """
        Insert a GeometryLine object directly, verifying SurrealDB
        returns a GeometryLine instance on decode.
        """
        line = GeometryLine(
            GeometryPoint(0, 0),
            GeometryPoint(1, 1),
            GeometryPoint(2, 2),
        )

        create_query = """
            CREATE geometry_tests:obj_line1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": line})

        results = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo_obj = results[0]["geometry"]

        self.assertIsInstance(stored_geo_obj, GeometryLine)
        self.assertEqual(stored_geo_obj, line)


class TestGeometryPolygon(BaseTestGeometry):
    """
    Tests for the GeometryPolygon class.
    """

    async def test_class_methods(self):
        line1 = GeometryLine(GeometryPoint(0, 0), GeometryPoint(1, 1))
        line2 = GeometryLine(GeometryPoint(1, 1), GeometryPoint(2, 2))
        poly = GeometryPolygon(line1, line2)

        # get_coordinates
        self.assertEqual(
            poly.get_coordinates(),
            [
                [(0, 0), (1, 1)],
                [(1, 1), (2, 2)],
            ],
        )

        # parse_coordinates
        coords = [
            [(0, 0), (1, 1)],
            [(1, 1), (2, 2), (3, 3)],
        ]
        parsed_poly = GeometryPolygon.parse_coordinates(coords)
        self.assertEqual(parsed_poly.get_coordinates(), coords)

        # equality
        self.assertTrue(poly != parsed_poly)

    async def test_db_insert_and_retrieve_polygon(self):
        geometry_dict = {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [1, 1], [2, 2], [0, 0]]  # close the ring
            ],
        }
        create_query = """
            CREATE geometry_tests:polygon1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": geometry_dict})

        select_result = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo = select_result[0]["geometry"]
        self.assertEqual(stored_geo["type"], "Polygon")
        self.assertEqual(stored_geo["coordinates"], [[[0, 0], [1, 1], [2, 2], [0, 0]]])


class TestGeometryMultiPoint(BaseTestGeometry):
    async def test_class_methods(self):
        mp = GeometryMultiPoint(
            GeometryPoint(1, 2),
            GeometryPoint(3, 4),
            GeometryPoint(5, 6),
        )
        self.assertEqual(mp.get_coordinates(), [(1, 2), (3, 4), (5, 6)])

        parsed = GeometryMultiPoint.parse_coordinates([(1, 2), (3, 4), (5, 6)])
        self.assertEqual(mp, parsed)

    async def test_db_insert_and_retrieve_multipoint(self):
        geometry_dict = {
            "type": "MultiPoint",
            "coordinates": [[1, 2], [3, 4], [5, 6]],
        }
        create_query = """
            CREATE geometry_tests:multipoint1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": geometry_dict})

        select_result = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo = select_result[0]["geometry"]
        self.assertEqual(stored_geo["type"], "MultiPoint")
        self.assertEqual(stored_geo["coordinates"], [[1, 2], [3, 4], [5, 6]])

    async def test_db_insert_and_retrieve_multipoint_as_python_object(self):
        """
        Insert a GeometryMultiPoint object, retrieve it as GeometryMultiPoint.
        """
        mp = GeometryMultiPoint(
            GeometryPoint(1, 2),
            GeometryPoint(3, 4),
            GeometryPoint(5, 6)
        )

        create_query = """
            CREATE geometry_tests:obj_multipoint1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": mp})

        results = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo_obj = results[0]["geometry"]

        self.assertIsInstance(stored_geo_obj, GeometryMultiPoint)
        self.assertEqual(stored_geo_obj, mp)


class TestGeometryMultiLine(BaseTestGeometry):
    async def test_class_methods(self):
        l1 = GeometryLine(GeometryPoint(0, 0), GeometryPoint(1, 1))
        l2 = GeometryLine(GeometryPoint(2, 2), GeometryPoint(3, 3))
        ml = GeometryMultiLine(l1, l2)
        self.assertEqual(ml.get_coordinates(), [[(0, 0), (1, 1)], [(2, 2), (3, 3)]])

        coords = [[(0, 0), (1, 1)], [(2, 2), (3, 3)]]
        parsed = GeometryMultiLine.parse_coordinates(coords)
        self.assertEqual(ml, parsed)

    async def test_db_insert_and_retrieve_multiline(self):
        geometry_dict = {
            "type": "MultiLineString",
            "coordinates": [
                [[0, 0], [1, 1]],
                [[2, 2], [3, 3]],
            ],
        }
        create_query = """
            CREATE geometry_tests:multiline1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": geometry_dict})

        select_result = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo = select_result[0]["geometry"]
        self.assertEqual(stored_geo["type"], "MultiLineString")
        self.assertEqual(stored_geo["coordinates"], [[[0, 0], [1, 1]], [[2, 2], [3, 3]]])

    async def test_db_insert_and_retrieve_multiline_as_python_object(self):
        """
        Insert a GeometryMultiLine object, retrieve it as GeometryMultiLine.
        """
        line1 = GeometryLine(GeometryPoint(0, 0), GeometryPoint(1, 1))
        line2 = GeometryLine(GeometryPoint(2, 2), GeometryPoint(3, 3))
        ml = GeometryMultiLine(line1, line2)

        create_query = """
            CREATE geometry_tests:obj_multiline1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": ml})

        results = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo_obj = results[0]["geometry"]

        self.assertIsInstance(stored_geo_obj, GeometryMultiLine)
        self.assertEqual(stored_geo_obj, ml)


class TestGeometryMultiPolygon(BaseTestGeometry):
    async def test_class_methods(self):
        p1 = GeometryPolygon(
            GeometryLine(GeometryPoint(0, 0), GeometryPoint(1, 1)),
            GeometryLine(GeometryPoint(1, 1), GeometryPoint(0, 2)),
        )
        p2 = GeometryPolygon(
            GeometryLine(GeometryPoint(5, 5), GeometryPoint(6, 6)),
            GeometryLine(GeometryPoint(6, 6), GeometryPoint(5, 7)),
        )
        mp = GeometryMultiPolygon(p1, p2)
        self.assertEqual(len(mp.geometry_polygons), 2)

        coords = [
            [[(0, 0), (1, 1)], [(1, 1), (0, 2)]],
            [[(5, 5), (6, 6)], [(6, 6), (5, 7)]],
        ]
        parsed = GeometryMultiPolygon.parse_coordinates(coords)
        self.assertEqual(mp, parsed)

    async def test_db_insert_and_retrieve_multipolygon(self):
        geometry_dict = {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [[0, 0], [1, 1], [1, 0], [0, 0]]
                ],
                [
                    [[5, 5], [6, 6], [6, 5], [5, 5]]
                ],
            ],
        }
        create_query = """
            CREATE geometry_tests:multipolygon1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": geometry_dict})

        select_result = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo = select_result[0]["geometry"]
        self.assertEqual(stored_geo["type"], "MultiPolygon")
        self.assertEqual(
            stored_geo["coordinates"],
            [
                [[[0, 0], [1, 1], [1, 0], [0, 0]]],
                [[[5, 5], [6, 6], [6, 5], [5, 5]]],
            ],
        )


class TestGeometryCollection(BaseTestGeometry):
    async def test_class_methods(self):
        pt = GeometryPoint(1.1, 2.2)
        ln = GeometryLine(GeometryPoint(0, 0), GeometryPoint(1, 1))
        gc = GeometryCollection(pt, ln)
        self.assertEqual(len(gc.geometries), 2)
        self.assertTrue(gc == GeometryCollection(pt, ln))

    async def test_db_insert_and_retrieve_collection(self):
        geometry_dict = {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Point", "coordinates": [1.1, 2.2]},
                {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            ],
        }
        create_query = """
            CREATE geometry_tests:collection1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": geometry_dict})

        select_result = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo = select_result[0]["geometry"]
        self.assertEqual(stored_geo["type"], "GeometryCollection")
        self.assertEqual(len(stored_geo["geometries"]), 2)

    async def test_db_insert_and_retrieve_collection_as_python_object(self):
        """
        Insert a GeometryCollection object, retrieve it as GeometryCollection.
        """
        pt = GeometryPoint(1.1, 2.2)
        ln = GeometryLine(GeometryPoint(0.0, 0.0), GeometryPoint(1.0, 1.0))
        gc = GeometryCollection(pt, ln)

        create_query = """
            CREATE geometry_tests:obj_collection1 SET geometry = $geo;
        """
        await self.connection.query(create_query, params={"geo": gc})

        results = await self.connection.query(
            "SELECT * FROM geometry_tests;"
        )
        stored_geo_obj = results[0]["geometry"]

        self.assertIsInstance(stored_geo_obj, GeometryCollection)
        self.assertEqual(stored_geo_obj, gc)


if __name__ == "__main__":
    unittest.main()
