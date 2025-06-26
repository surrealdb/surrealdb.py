import uuid

from surrealdb.request_message.descriptors.cbor_ws import WsCborDescriptor
from surrealdb.request_message.methods import RequestMethod


class RequestMessage:
    WS_CBOR_DESCRIPTOR = WsCborDescriptor()

    def __init__(self, method: RequestMethod, **kwargs) -> None:
        self.id = str(uuid.uuid4())
        self.method = method
        self.kwargs = kwargs
