class GeometryPoint:
    def __init__(self, longitude: float, latitude: float):
        self.longitude = longitude
        self.latitude = latitude

    def __repr__(self):
        return 'GeometryPoint(longitude={self.longitude}, latitude={self.latitude})'.format(self=self)

    def get_coordinates(self) -> list[float]:
        return [self.longitude, self.latitude]

    @staticmethod
    def get_point_from_coordinates(self, coordinates):
        return GeometryPoint(coordinates[0], coordinates[1])


class GeometryLine:
    geometric_points: GeometryPoint

    def __init__(self, geometry_points):
        self.geometry_points = geometry_points

    def get_coordinates(self):
        points = []
        for point in self.geometry_points:
            points.append(point.get_cordinates)
        return points


class GeometryPolygon:
    def __init__(self, geometry_lines):
        self.geometry_lines = geometry_lines


class GeometryMultiPoint:
    def __init__(self, geometry_points):
        self.geometry_points = geometry_points


class GeometryMultiLine:
    def __init__(self, geometry_lines):
        self.geometry_lines = geometry_lines


class GeometryMultiPolygon:
    def __init__(self, geometry_polygons):
        self.geometry_polygons = geometry_polygons


class GeometryCollection:
    def __init__(self, geometry_collection):
        self.geometry_collection = geometry_collection
