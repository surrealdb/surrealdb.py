import uuid
from typing import Any, Optional
import warnings

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

        legacy_keys = {"collection", "record_id", "data", "table", "uuid", "key", "value"}
        using_old_style = False
        if params is not None and not kwargs:
            # New params-only API - perform Pydantic validation
            self.kwargs = {"params": params}
            self._validate_request(method, params)
        else:
            # Old kwargs-based API - store as-is for backward compatibility
            if params is not None:
                kwargs["params"] = params
            self.kwargs = kwargs
            # Deprecation warning if using old style
            if not ("params" in kwargs and isinstance(kwargs["params"], list)):
                using_old_style = True
            if any(k in kwargs for k in legacy_keys):
                using_old_style = True
            if using_old_style:
                warnings.warn(
                    "The kwargs-based API for RequestMessage is deprecated and will be removed in a future major release. Please use the explicit params list style.",
                    DeprecationWarning,
                    stacklevel=2,
                )

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
