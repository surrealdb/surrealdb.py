"""
Request Validation Schemas

This module contains Pydantic schemas for validating SurrealDB request messages.
Each schema corresponds to a specific SurrealDB method and defines the expected
structure and validation rules for request parameters.
"""

from typing import Any, Literal, Union

from pydantic import BaseModel, Field


# Base request schema without method field to avoid inheritance conflicts
class BaseRequest(BaseModel):
    """Base schema for all SurrealDB requests"""

    id: str = Field(..., description="Request ID")


# Method-specific request schemas
class UseRequest(BaseRequest):
    """Schema for 'use' method - sets namespace and database"""

    method: Literal["use"] = Field(default="use", description="SurrealDB method name")
    params: list[str] = Field(
        ..., min_length=2, max_length=2, description="[namespace, database]"
    )


class InfoRequest(BaseRequest):
    """Schema for 'info' method - gets database information"""

    method: Literal["info"] = Field(default="info", description="SurrealDB method name")


class VersionRequest(BaseRequest):
    """Schema for 'version' method - gets server version"""

    method: Literal["version"] = Field(
        default="version", description="SurrealDB method name"
    )


class AuthenticateRequest(BaseRequest):
    """Schema for 'authenticate' method - authenticates with a JWT token"""

    method: Literal["authenticate"] = Field(
        default="authenticate", description="SurrealDB method name"
    )
    params: list[str] = Field(
        ..., min_length=1, max_length=1, description="[jwt_token]"
    )

    def __init__(self, **data):
        super().__init__(**data)
        # Validate JWT format using regex
        if hasattr(self, "params") and self.params:
            token = self.params[0]
            import re

            jwt_pattern = r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"
            if not re.match(jwt_pattern, token):
                raise ValueError(f"Invalid JWT token format: {token}")


class InvalidateRequest(BaseRequest):
    """Schema for 'invalidate' method - invalidates authentication"""

    method: Literal["invalidate"] = Field(
        default="invalidate", description="SurrealDB method name"
    )


class LetRequest(BaseRequest):
    """Schema for 'let' method - sets a variable"""

    method: Literal["let"] = Field(default="let", description="SurrealDB method name")
    params: list[Any] = Field(
        ..., min_length=2, max_length=2, description="[key, value]"
    )


class UnsetRequest(BaseRequest):
    """Schema for 'unset' method - unsets variables"""

    method: Literal["unset"] = Field(
        default="unset", description="SurrealDB method name"
    )
    params: list[str] = Field(..., min_length=1, description="[variable_names...]")


class LiveRequest(BaseRequest):
    """Schema for 'live' method - creates live query"""

    method: Literal["live"] = Field(default="live", description="SurrealDB method name")
    params: list[Any] = Field(..., min_length=1, max_length=1, description="[table]")


class KillRequest(BaseRequest):
    """Schema for 'kill' method - kills live query"""

    method: Literal["kill"] = Field(default="kill", description="SurrealDB method name")
    params: list[str] = Field(..., min_length=1, max_length=1, description="[uuid]")


class QueryRequest(BaseRequest):
    """Schema for 'query' method - executes SurrealQL"""

    method: Literal["query"] = Field(
        default="query", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=2, max_length=2, description="[query, params]"
    )


class InsertRequest(BaseRequest):
    """Schema for 'insert' method - inserts records"""

    method: Literal["insert"] = Field(
        default="insert", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=2, max_length=2, description="[collection, data]"
    )


class PatchRequest(BaseRequest):
    """Schema for 'patch' method - patches records"""

    method: Literal["patch"] = Field(
        default="patch", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=2, max_length=2, description="[collection, patches]"
    )


class SelectRequest(BaseRequest):
    """Schema for 'select' method - selects records"""

    method: Literal["select"] = Field(
        default="select", description="SurrealDB method name"
    )
    params: list[Any] = Field(..., min_length=1, description="[target, ...]")


class CreateRequest(BaseRequest):
    """Schema for 'create' method - creates records"""

    method: Literal["create"] = Field(
        default="create", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=1, max_length=2, description="[collection, data?]"
    )


class UpdateRequest(BaseRequest):
    """Schema for 'update' method - updates records"""

    method: Literal["update"] = Field(
        default="update", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=1, max_length=2, description="[record_id, data?]"
    )


class MergeRequest(BaseRequest):
    """Schema for 'merge' method - merges records"""

    method: Literal["merge"] = Field(
        default="merge", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=1, max_length=2, description="[record_id, data?]"
    )


class DeleteRequest(BaseRequest):
    """Schema for 'delete' method - deletes records"""

    method: Literal["delete"] = Field(
        default="delete", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=1, max_length=1, description="[record_id]"
    )


class InsertRelationRequest(BaseRequest):
    """Schema for 'insert_relation' method - inserts relation records"""

    method: Literal["insert_relation"] = Field(
        default="insert_relation", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=2, max_length=2, description="[table, data]"
    )


class UpsertRequest(BaseRequest):
    """Schema for 'upsert' method - upserts records"""

    method: Literal["upsert"] = Field(
        default="upsert", description="SurrealDB method name"
    )
    params: list[Any] = Field(
        ..., min_length=1, max_length=2, description="[record_id, data?]"
    )


class SignUpRequest(BaseRequest):
    """Schema for 'signup' method - user signup"""

    method: Literal["signup"] = Field(
        default="signup", description="SurrealDB method name"
    )
    params: list[dict[str, Any]] = Field(
        ..., min_length=1, max_length=1, description="[signup_data]"
    )


class SignInRequest(BaseRequest):
    """Schema for 'signin' method - user signin"""

    method: Literal["signin"] = Field(
        default="signin", description="SurrealDB method name"
    )
    params: list[dict[str, Any]] = Field(
        ..., min_length=1, max_length=1, description="[signin_data]"
    )


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
