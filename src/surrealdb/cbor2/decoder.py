from warnings import warn

from surrealdb.cbor2._decoder import CBORDecoder as CBORDecoder
from surrealdb.cbor2._decoder import load as load
from surrealdb.cbor2._decoder import loads as loads

warn(
    "The cbor.decoder module has been deprecated. Instead import everything directly from cbor2."
)
