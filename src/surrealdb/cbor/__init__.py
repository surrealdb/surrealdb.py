from typing import Any

from surrealdb.cbor._decoder import CBORDecoder as CBORDecoder
from surrealdb.cbor._decoder import load as load
from surrealdb.cbor._decoder import loads as loads
from surrealdb.cbor._encoder import CBOREncoder as CBOREncoder
from surrealdb.cbor._encoder import dump as dump
from surrealdb.cbor._encoder import dumps as dumps
from surrealdb.cbor._encoder import shareable_encoder as shareable_encoder
from surrealdb.cbor._types import CBORDecodeEOF as CBORDecodeEOF
from surrealdb.cbor._types import CBORDecodeError as CBORDecodeError
from surrealdb.cbor._types import CBORDecodeValueError as CBORDecodeValueError
from surrealdb.cbor._types import CBOREncodeError as CBOREncodeError
from surrealdb.cbor._types import CBOREncodeTypeError as CBOREncodeTypeError
from surrealdb.cbor._types import CBOREncodeValueError as CBOREncodeValueError
from surrealdb.cbor._types import CBORError as CBORError
from surrealdb.cbor._types import CBORSimpleValue as CBORSimpleValue
from surrealdb.cbor._types import CBORTag as CBORTag
from surrealdb.cbor._types import FrozenDict as FrozenDict
from surrealdb.cbor._types import undefined as undefined

# Re-export imports so they look like they live directly in this package
key: str
value: Any
for key, value in list(locals().items()):
    if callable(value) and getattr(value, "__module__", "").startswith("cbor."):
        value.__module__ = __name__
