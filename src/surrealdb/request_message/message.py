from surrealdb.request_message.descriptors.cbor_ws import WsCborDescriptor
from surrealdb.request_message.descriptors.json_http import JsonHttpDescriptor
from surrealdb.request_message.methods import RequestMethod


class RequestMessage:

    WS_CBOR_DESCRIPTOR = WsCborDescriptor()
    JSON_HTTP_DESCRIPTOR = JsonHttpDescriptor()

    def __init__(self, id_for_request, method: RequestMethod, **kwargs) -> None:
        self.id = id_for_request
        self.method = method
        self.kwargs = kwargs
