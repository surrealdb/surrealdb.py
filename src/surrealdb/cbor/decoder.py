from warnings import warn

from surrealdb.cbor._decoder import CBORDecoder as CBORDecoder
from surrealdb.cbor._decoder import load as load
from surrealdb.cbor._decoder import loads as loads

warn(
    "The cbor.decoder module has been deprecated. Instead import everything directly from cbor."
)
