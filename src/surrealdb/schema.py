from typing import Annotated, Any, Optional, Union

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Literal


class UseRequest(BaseModel):
    id: Any
    method: Literal["use"]
    params: Annotated[list[str], Field(min_length=2, max_length=2)]


class InfoRequest(BaseModel):
    id: Any
    method: Literal["info"]


class VersionRequest(BaseModel):
    id: Any
    method: Literal["version"]


class AuthenticateRequest(BaseModel):
    id: Any
    method: Literal["authenticate"]
    params: Annotated[
        list[
            Annotated[
                str,
                StringConstraints(
                    pattern=r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"
                ),
            ]
        ],
        Field(min_length=1, max_length=1),
    ]


class InvalidateRequest(BaseModel):
    id: Any
    method: Literal["invalidate"]


class LetRequest(BaseModel):
    id: Any
    method: Literal["let"]
    params: Annotated[list[Any], Field(min_length=2, max_length=2)]


class UnsetRequest(BaseModel):
    id: Any
    method: Literal["unset"]
    params: list[Any]


class LiveRequest(BaseModel):
    id: Any
    method: Literal["live"]
    params: Annotated[list[Any], Field(min_length=1, max_length=1)]


class KillRequest(BaseModel):
    id: Any
    method: Literal["kill"]
    params: Annotated[list[Any], Field(min_length=1, max_length=1)]


class QueryRequest(BaseModel):
    id: Any
    method: Literal["query"]
    params: Annotated[list[Any], Field(min_length=2, max_length=2)]


class InsertRequest(BaseModel):
    id: Any
    method: Literal["insert"]
    params: Annotated[list[Any], Field(min_length=2, max_length=2)]


class PatchRequest(BaseModel):
    id: Any
    method: Literal["patch"]
    params: Annotated[list[Any], Field(min_length=2, max_length=2)]


class SelectRequest(BaseModel):
    id: Any
    method: Literal["select"]
    params: list[Any]


class CreateRequest(BaseModel):
    id: Any
    method: Literal["create"]
    params: Annotated[list[Any], Field(min_length=1, max_length=2)]


class UpdateRequest(BaseModel):
    id: Any
    method: Literal["update"]
    params: Annotated[list[Any], Field(min_length=1, max_length=2)]


class MergeRequest(BaseModel):
    id: Any
    method: Literal["merge"]
    params: Annotated[list[Any], Field(min_length=1, max_length=2)]


class DeleteRequest(BaseModel):
    id: Any
    method: Literal["delete"]
    params: Annotated[list[Any], Field(min_length=1, max_length=1)]


class InsertRelationRequest(BaseModel):
    id: Any
    method: Literal["insert_relation"]
    params: Annotated[list[Any], Field(min_length=2, max_length=2)]


class UpsertRequest(BaseModel):
    id: Any
    method: Literal["upsert"]
    params: Annotated[list[Any], Field(min_length=1, max_length=2)]


# Sign-up and Sign-in are more complex due to variable parameter structures
class SignUpRequest(BaseModel):
    id: Any
    method: Literal["signup"]
    params: list[
        dict[str, Any]
    ]  # Complex nested structure with NS, DB, AC, and variables


class SignInRequest(BaseModel):
    id: Any
    method: Literal["signin"]
    params: list[dict[str, Any]]  # Variable structure depending on auth type


# Union type for all possible request types
RequestType = Union[
    UseRequest,
    InfoRequest,
    VersionRequest,
    AuthenticateRequest,
    InvalidateRequest,
    LetRequest,
    UnsetRequest,
    LiveRequest,
    KillRequest,
    QueryRequest,
    InsertRequest,
    PatchRequest,
    SelectRequest,
    CreateRequest,
    UpdateRequest,
    MergeRequest,
    DeleteRequest,
    InsertRelationRequest,
    UpsertRequest,
    SignUpRequest,
    SignInRequest,
]


def validate_request(data: dict) -> RequestType:
    """
    Validate a request dictionary against the appropriate schema based on the method.

    Args:
        data: Dictionary containing id, method, and optional params

    Returns:
        Validated request object

    Raises:
        ValueError: If the data doesn't match any schema or fails validation
    """
    method = data.get("method")

    if not isinstance(method, str):
        raise ValueError(f"Method must be a string, got: {type(method)}")

    # Map method names to their corresponding request classes
    method_map = {
        "use": UseRequest,
        "info": InfoRequest,
        "version": VersionRequest,
        "authenticate": AuthenticateRequest,
        "invalidate": InvalidateRequest,
        "let": LetRequest,
        "unset": UnsetRequest,
        "live": LiveRequest,
        "kill": KillRequest,
        "query": QueryRequest,
        "insert": InsertRequest,
        "patch": PatchRequest,
        "select": SelectRequest,
        "create": CreateRequest,
        "update": UpdateRequest,
        "merge": MergeRequest,
        "delete": DeleteRequest,
        "insert_relation": InsertRelationRequest,
        "upsert": UpsertRequest,
        "signup": SignUpRequest,
        "signin": SignInRequest,
    }

    if method not in method_map:
        raise ValueError(f"Unknown method: {method}")

    request_class = method_map[method]
    return request_class.model_validate(data)


# Example usage:
if __name__ == "__main__":
    # Valid authenticate request
    auth_data = {
        "id": "123",
        "method": "authenticate",
        "params": [
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWV9.TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ"
        ],
    }

    try:
        validated_request = validate_request(auth_data)
        print(f"Valid request: {validated_request}")
    except Exception as e:
        print(f"Validation error: {e}")

    # Invalid authenticate request (empty params)
    invalid_auth_data = {"id": "123", "method": "authenticate", "params": []}

    try:
        validate_request(invalid_auth_data)
    except Exception as e:
        print(f"Expected validation error: {e}")
