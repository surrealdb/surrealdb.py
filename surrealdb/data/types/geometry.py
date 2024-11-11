from dataclasses import dataclass
from typing import List, Any, Tuple


class Geometry:
    def get_coordinates(self):
        pass

    @staticmethod
    def parse_coordinates(coordinates):
        pass


@dataclass
class GeometryPoint(Geometry):
    longitude: float
    latitude: float

    def __repr__(self):
        return 'GeometryPoint(longitude={self.longitude}, latitude={self.latitude})'.format(self=self)

    def get_coordinates(self) -> Tuple[float, float]:
        return self.longitude, self.latitude

    @staticmethod
    def parse_coordinates(coordinates):
        return GeometryPoint(coordinates[0], coordinates[1])


class GeometryLine(Geometry):

    def __init__(self, point1: GeometryPoint, point2: GeometryPoint, *other_points: GeometryPoint):
        self.geometry_points = [point1, point2] + list(other_points)

    def get_coordinates(self) -> List[Tuple[float, float]]:
        return [point.get_coordinates() for point in self.geometry_points]

    @staticmethod
    def parse_coordinates(coordinates):
        return GeometryLine(*[GeometryPoint.parse_coordinates(point) for point in coordinates])


class GeometryPolygon(Geometry):
    def __init__(self, line1, line2, *other_lines: GeometryLine):
        self.geometry_lines = [line1, line2] + list(other_lines)

    def get_coordinates(self) -> List[List[Tuple[float, float]]]:
        return [line.get_coordinates() for line in self.geometry_lines]

    @staticmethod
    def parse_coordinates(coordinates):
        return GeometryPolygon(*[GeometryLine.parse_coordinates(line) for line in coordinates])


class GeometryMultiPoint(Geometry):
    def __init__(self, *geometry_points: GeometryPoint):
        self.geometry_points = geometry_points

    def get_coordinates(self) -> List[Tuple[float, float]]:
        return [point.get_coordinates() for point in self.geometry_points]

    @staticmethod
    def parse_coordinates(coordinates):
        return GeometryMultiPoint(*[GeometryPoint.parse_coordinates(point) for point in coordinates])


class GeometryMultiLine(Geometry):
    def __init__(self, *geometry_lines: GeometryLine):
        self.geometry_lines = geometry_lines

    def get_coordinates(self) -> List[List[Tuple[float, float]]]:
        return [line.get_coordinates() for line in self.geometry_lines]

    @staticmethod
    def parse_coordinates(coordinates):
        return GeometryMultiLine(*[GeometryLine.parse_coordinates(line) for line in coordinates])


class GeometryMultiPolygon(Geometry):
    def __init__(self, *geometry_polygons: GeometryPolygon):
        self.geometry_polygons = geometry_polygons

    def get_coordinates(self) -> List[List[List[Tuple[float, float]]]]:
        return [polygon.get_coordinates() for polygon in self.geometry_polygons]

    @staticmethod
    def parse_coordinates(coordinates):
        return GeometryMultiPolygon(*[GeometryPolygon.parse_coordinates(polygon) for polygon in coordinates])


@dataclass()
class GeometryCollection:

    def __init__(self, *geometries: Geometry):
        self.geometries = geometries
