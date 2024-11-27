import uuid
from unittest import TestCase

from surrealdb.data import GeometryPoint, GeometryLine, Table, GeometryPolygon, GeometryCollection
from surrealdb.data.cbor import encode, decode


class TestCBOR(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_geometry(self):
        point1 = GeometryPoint(10.00, -3.21)
        point2 = GeometryPoint(3.10, 0.1)
        point3 = GeometryPoint(4.22, 1.51)

        line1 = GeometryLine(point1, point2, point3, point1)
        line2 = GeometryLine(point2, point3)
        line3 = GeometryLine(point3, point1)

        polygon1 = GeometryPolygon(line1, line2, line3)

        collection1 = GeometryCollection(point1, line1, polygon1)

        data1 = encode(point1)
        data2 = encode(line1)
        data3 = encode(polygon1)
        data4 = encode(collection1)

        # print("Point: ", data1.hex())
        # print("Line: ", data2.hex())
        # print("Polygon: ", data3.hex())
        # print("Encoded Collection: ", data4.hex())
        #
        # print("Decoded Point 1", decode(data1))
        # print("Decoded Line 1", decode(data2))
        # print("Decoded Polygon 1", decode(data3))
        # print("Decoded Collection 1", decode(data4))

    def test_table(self):
        table = Table('testtable')

    def test_uuid(self):
        uid = uuid.uuid4()
        encoded = encode(uid)
        decoded = decode(encoded)

