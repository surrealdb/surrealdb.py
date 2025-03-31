from warnings import warn

from surrealdb.cbor2._types import CBORDecodeEOF as CBORDecodeEOF
from surrealdb.cbor2._types import CBORDecodeError as CBORDecodeError
from surrealdb.cbor2._types import CBORDecodeValueError as CBORDecodeValueError
from surrealdb.cbor2._types import CBOREncodeError as CBOREncodeError
from surrealdb.cbor2._types import CBOREncodeTypeError as CBOREncodeTypeError
from surrealdb.cbor2._types import CBOREncodeValueError as CBOREncodeValueError
from surrealdb.cbor2._types import CBORError as CBORError
from surrealdb.cbor2._types import CBORSimpleValue as CBORSimpleValue
from surrealdb.cbor2._types import CBORTag as CBORTag
from surrealdb.cbor2._types import FrozenDict as FrozenDict
from surrealdb.cbor2._types import undefined as undefined

warn(
    "The cbor2.types module has been deprecated. Instead import everything directly from cbor2."
)
