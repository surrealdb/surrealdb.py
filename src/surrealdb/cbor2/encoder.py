from warnings import warn

from surrealdb.cbor2._encoder import CBOREncoder as CBOREncoder
from surrealdb.cbor2._encoder import dump as dump
from surrealdb.cbor2._encoder import dumps as dumps
from surrealdb.cbor2._encoder import shareable_encoder as shareable_encoder

warn(
    "The cbor2.encoder module has been deprecated. Instead import everything directly from cbor2."
)
