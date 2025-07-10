import uuid
from typing import Any, Optional

from surrealdb.request_message.descriptors.cbor_ws import WsCborDescriptor
from surrealdb.request_message.methods import RequestMethod
from surrealdb.request_message.validation import validate_request


class RequestMessage:
    WS_CBOR_DESCRIPTOR = WsCborDescriptor()

    def __init__(
        self, method: RequestMethod, params: Optional[list[Any]] = None, **kwargs
    ) -> None:
        self.id = str(uuid.uuid4())
        self.method = method

        # Handle both old kwargs style and new params style for backward compatibility
        if params is not None and not kwargs:
            # New params-only API - perform Pydantic validation
            self.kwargs = {"params": params}
            self._validate_request(method, params)
        else:
            # Old kwargs-based API - store as-is for backward compatibility
            # (This includes cases where params is passed as a kwarg alongside other kwargs)
            if params is not None:
                kwargs["params"] = params
            self.kwargs = kwargs

    def _validate_request(self, method: RequestMethod, params: list[Any]) -> None:
        """Validate request using Pydantic schemas"""
        try:
            # Convert enum to string for validation
            method_str = method.value if hasattr(method, "value") else str(method)
            validation_data = {"id": self.id, "method": method_str, "params": params}
            # This will raise ValueError if validation fails
            validate_request(validation_data)
        except Exception as e:
            # Re-raise with more context
            raise ValueError(
                f"Request validation failed for method '{method}': {str(e)}"
            ) from e
