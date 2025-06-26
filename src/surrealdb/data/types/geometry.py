"""
Defines a unset of geometry classes for representing geometric shapes such as points, lines, polygons, and collections.
"""

from dataclasses import dataclass


class Geometry:
    """
    Base class for all geometry types. Provides the interface for retrieving coordinates
    and parsing them into specific geometry types.
    """

    def get_coordinates(self):
        """
        Returns the coordinates of the geometry. Should be implemented by subclasses.
        """
        pass

    @staticmethod
    def parse_coordinates(coordinates):
        """
        Parses a list of coordinates into a specific geometry type. Should be implemented by subclasses.
        """
        pass


@dataclass
class GeometryPoint(Geometry):
    """
    Represents a single point in a 2D space.

    Attributes:
        longitude: The longitude of the point.
        latitude: The latitude of the point.
    """

    longitude: float
    latitude: float

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(longitude={self.longitude}, latitude={self.latitude})"

    def get_coordinates(self) -> tuple[float, float]:
        """
        Returns the coordinates of the point.

        Returns:
            A tuple of (longitude, latitude).
        """
        return self.longitude, self.latitude

    @staticmethod
    def parse_coordinates(coordinates: tuple[float, float]) -> "GeometryPoint":
        """
        Parses a tuple of coordinates into a GeometryPoint.

        Args:
            coordinates: A tuple containing longitude and latitude.

        Returns:
            A GeometryPoint object.
        """
        return GeometryPoint(coordinates[0], coordinates[1])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GeometryPoint):
            return self.longitude == other.longitude and self.latitude == other.latitude
        return False


@dataclass
class GeometryLine(Geometry):
    """
    Represents a line defined by two or more points.

    Attributes:
        geometry_points: A list of GeometryPoint objects defining the line.
    """

    geometry_points: list[GeometryPoint]

    def __init__(
        self, point1: GeometryPoint, point2: GeometryPoint, *other_points: GeometryPoint
    ) -> None:
        """
        The constructor for the GeometryLine class.
        """
        self.geometry_points = [point1, point2] + list(other_points)

    def get_coordinates(self) -> list[tuple[float, float]]:
        """
        Returns the coordinates of the line as a list of tuples.

        Returns:
            A list of (longitude, latitude) tuples.
        """
        return [point.get_coordinates() for point in self.geometry_points]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(geo) for geo in self.geometry_points)})"

    @staticmethod
    def parse_coordinates(coordinates: list[tuple[float, float]]) -> "GeometryLine":
        """
        Parses a list of coordinate tuples into a GeometryLine.

        Args:
            coordinates: A list of tuples containing longitude and latitude.

        Returns:
            A GeometryLine object.
        """
        return GeometryLine(
            *[GeometryPoint.parse_coordinates(point) for point in coordinates]
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GeometryLine):
            return self.geometry_points == other.geometry_points
        return False


@dataclass
class GeometryPolygon(Geometry):
    """
    Represents a polygon defined by multiple lines.

    Attributes:
        geometry_lines: A list of GeometryLine objects defining the polygon.
    """

    geometry_lines: list[GeometryLine]

    def __init__(
        self, line1: GeometryLine, line2: GeometryLine, *other_lines: GeometryLine
    ):
        self.geometry_lines = [line1, line2] + list(other_lines)

    def get_coordinates(self) -> list[list[tuple[float, float]]]:
        """
        Returns the coordinates of the polygon as a list of lines, each containing a list of coordinate tuples.

        Returns:
            A list of lists of (longitude, latitude) tuples.
        """
        return [line.get_coordinates() for line in self.geometry_lines]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(geo) for geo in self.geometry_lines)})"

    @staticmethod
    def parse_coordinates(
        coordinates: list[list[tuple[float, float]]],
    ) -> "GeometryPolygon":
        """
        Parses a list of lines, each defined by a list of coordinate tuples, into a GeometryPolygon.

        Args:
            coordinates: A list of lists containing longitude and latitude tuples.

        Returns:
            A GeometryPolygon object.
        """
        return GeometryPolygon(
            *[GeometryLine.parse_coordinates(line) for line in coordinates]
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GeometryPolygon):
            return self.geometry_lines == other.geometry_lines
        return False


@dataclass
class GeometryMultiPoint(Geometry):
    """
    Represents multiple points in 2D space.

    Attributes:
        geometry_points: A list of GeometryPoint objects.
    """

    geometry_points: list[GeometryPoint]

    def __init__(self, *geometry_points: GeometryPoint):
        self.geometry_points = list(geometry_points)

    def get_coordinates(self) -> list[tuple[float, float]]:
        """
        Returns the coordinates of all points as a list of tuples.

        Returns:
            A list of (longitude, latitude) tuples.
        """
        return [point.get_coordinates() for point in self.geometry_points]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(geo) for geo in self.geometry_points)})"

    @staticmethod
    def parse_coordinates(
        coordinates: list[tuple[float, float]],
    ) -> "GeometryMultiPoint":
        """
        Parses a list of coordinate tuples into a GeometryMultiPoint.

        Args:
            coordinates: A list of tuples containing longitude and latitude.

        Returns:
            A GeometryMultiPoint object.
        """
        return GeometryMultiPoint(
            *[GeometryPoint.parse_coordinates(point) for point in coordinates]
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GeometryMultiPoint):
            return self.geometry_points == other.geometry_points
        return False


@dataclass
class GeometryMultiLine(Geometry):
    """
    Represents multiple lines.

    Attributes:
        geometry_lines: A list of GeometryLine objects.
    """

    geometry_lines: list[GeometryLine]

    def __init__(self, *geometry_lines: GeometryLine):
        self.geometry_lines = list(geometry_lines)

    def get_coordinates(self) -> list[list[tuple[float, float]]]:
        """
        Returns the coordinates of all lines as a list of lists of tuples.

        Returns:
            A list of lists of (longitude, latitude) tuples.
        """
        return [line.get_coordinates() for line in self.geometry_lines]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(geo) for geo in self.geometry_lines)})"

    @staticmethod
    def parse_coordinates(
        coordinates: list[list[tuple[float, float]]],
    ) -> "GeometryMultiLine":
        """
        Parses a list of lines, each defined by a list of coordinate tuples, into a GeometryMultiLine.

        Args:
            coordinates: A list of lists containing longitude and latitude tuples.

        Returns:
            A GeometryMultiLine object.
        """
        return GeometryMultiLine(
            *[GeometryLine.parse_coordinates(line) for line in coordinates]
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GeometryMultiLine):
            return self.geometry_lines == other.geometry_lines
        return False


@dataclass
class GeometryMultiPolygon(Geometry):
    """
    Represents multiple polygons.

    Attributes:
        geometry_polygons: A list of GeometryPolygon objects.
    """

    geometry_polygons: list[GeometryPolygon]

    def __init__(self, *geometry_polygons: GeometryPolygon):
        self.geometry_polygons = list(geometry_polygons)

    def get_coordinates(self) -> list[list[list[tuple[float, float]]]]:
        """
        Returns the coordinates of all polygons as a list of lists of lines, each containing a list of tuples.

        Returns:
            A list of lists of lists of (longitude, latitude) tuples.
        """
        return [polygon.get_coordinates() for polygon in self.geometry_polygons]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(geo) for geo in self.geometry_polygons)})"

    @staticmethod
    def parse_coordinates(
        coordinates: list[list[list[tuple[float, float]]]],
    ) -> "GeometryMultiPolygon":
        """
        Parses a list of polygons, each defined by a list of lines, into a GeometryMultiPolygon.

        Args:
            coordinates: A list of lists of lists containing longitude and latitude tuples.

        Returns:
            A GeometryMultiPolygon object.
        """
        return GeometryMultiPolygon(
            *[GeometryPolygon.parse_coordinates(polygon) for polygon in coordinates]
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GeometryMultiPolygon):
            return self.geometry_polygons == other.geometry_polygons
        return False


@dataclass
class GeometryCollection:
    """
    Represents a collection of multiple geometry objects.

    Attributes:
        geometries: A list of Geometry objects.
    """

    geometries: list[Geometry]

    def __init__(self, *geometries: Geometry):
        self.geometries = list(geometries)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(geo) for geo in self.geometries)})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GeometryCollection):
            return self.geometries == other.geometries
        return False
