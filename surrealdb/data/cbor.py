import cbor2

from surrealdb.data.types import constants
from surrealdb.data.types.geometry import GeometryPoint, GeometryLine, GeometryPolygon, GeometryMultiLine, \
    GeometryMultiPoint, GeometryMultiPolygon, GeometryCollection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@cbor2.shareable_encoder
def default_encoder(encoder, obj):
    if isinstance(obj, GeometryPoint):
        tagged = cbor2.CBORTag(constants.TAG_GEOMETRY_POINT, obj.get_coordinates())

    elif isinstance(obj, GeometryLine):
        tagged = cbor2.CBORTag(constants.TAG_GEOMETRY_LINE, obj.get_coordinates())

    elif isinstance(obj, GeometryPolygon):
        tagged = cbor2.CBORTag(constants.TAG_GEOMETRY_POLYGON)

    elif isinstance(obj, GeometryMultiLine):
        tagged = cbor2.CBORTag(constants.TAG_GEOMETRY_MULTI_LINE)

    elif isinstance(obj, GeometryMultiPoint):
        tagged = cbor2.CBORTag(constants.TAG_GEOMETRY_MULTI_POINT)

    elif isinstance(obj, GeometryMultiPolygon):
        tagged = cbor2.CBORTag(constants.TAG_GEOMETRY_MULTI_POLYGON)

    elif isinstance(obj, GeometryCollection):
        tagged = cbor2.CBORTag(constants.TAG_GEOMETRY_COLLECTION)

    elif isinstance(obj, RecordID):
        tagged = cbor2.CBORTag(constants.TAG_RECORD_ID, [obj.table_name, obj.id])

    elif isinstance(obj, Table):
        tagged = cbor2.CBORTag(constants.TAG_TABLE_NAME, obj.table_name)

    else:
        raise Exception('cannot encode')

    encoder.encode(tagged)


def tag_decoder(decoder, tag, shareable_index=None):
    if tag.tag == constants.TAG_GEOMETRY_POINT:
        return GeometryPoint(tag.value[0], tag.value[1])

    elif tag.tag == constants.TAG_GEOMETRY_LINE:
        points = []
        for coordinates in tag.value:
            points.append(GeometryPoint(coordinates[0], coordinates[1]))
        return GeometryLine(points)

    elif tag.tag == constants.TAG_NONE:
        return None

    else:
        return tag


def encode(obj):
    return cbor2.dumps(obj, default=default_encoder)


def decode(data):
    return cbor2.loads(data, tag_hook=tag_decoder)