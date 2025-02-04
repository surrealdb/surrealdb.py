from surrealdb.request_message.descriptors.cbor_ws import WsCborDescriptor
from surrealdb.request_message.methods import RequestMethod


class RequestMessage:

    WS_CBOR_DESCRIPTOR = WsCborDescriptor()

    def __init__(self, id_for_request, method: RequestMethod, **kwargs) -> None:
        self.id = id_for_request
        self.method = method
        self.kwargs = kwargs
