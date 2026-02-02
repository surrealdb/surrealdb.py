from __future__ import annotations

from uuid import UUID
from typing import TYPE_CHECKING, Any, cast

from pydantic_core import SchemaValidator
from pydantic_core import ValidationError as PydanticValidationError

from surrealdb.data.cbor import encode
from surrealdb.data.types.record_id import RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.data.utils import process_record
from surrealdb.request_message.methods import RequestMethod

if TYPE_CHECKING:
    from surrealdb.request_message.message import RequestMessage


def _method_field(expected: str | None) -> dict[str, Any]:
    if expected is None:
        return {"type": "str", "strict": True}
    return {"type": "literal", "expected": [expected]}


def _string_field() -> dict[str, Any]:
    return {"type": "str", "strict": True}


def _list_schema(
    items_schema: dict[str, Any] | None = None,
    *,
    min_length: int | None = None,
    max_length: int | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "list"}
    if items_schema is not None:
        schema["items_schema"] = items_schema
    if min_length is not None:
        schema["min_length"] = min_length
    if max_length is not None:
        schema["max_length"] = max_length
    return schema


def _build_validator(
    expected_method: str | None, params_schema: dict[str, Any] | None = None
) -> SchemaValidator:
    fields: dict[str, dict[str, Any]] = {
        "id": {"schema": _string_field(), "required": True},
        "method": {"schema": _method_field(expected_method), "required": True},
    }
    if params_schema is not None:
        fields["params"] = {"schema": params_schema, "required": True}
    return SchemaValidator({"type": "typed-dict", "fields": fields})


def _format_errors(exc: PydanticValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    )


def _inject_session_txn(data: dict[str, Any], obj: RequestMessage) -> None:
    session = obj.kwargs.get("session")
    if session is not None:
        data["session"] = str(session) if isinstance(session, UUID) else session
    txn = obj.kwargs.get("txn")
    if txn is not None:
        data["txn"] = str(txn) if isinstance(txn, UUID) else txn


USE_VALIDATOR = _build_validator(
    RequestMethod.USE.value,
    _list_schema({"type": "str", "strict": True}, min_length=2, max_length=2),
)
INFO_VALIDATOR = _build_validator(RequestMethod.INFO.value)
VERSION_VALIDATOR = _build_validator(RequestMethod.VERSION.value)
AUTHENTICATE_VALIDATOR = _build_validator(
    RequestMethod.AUTHENTICATE.value,
    _list_schema(
        {
            "type": "str",
            "strict": True,
            "pattern": r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$",
        },
        min_length=1,
        max_length=1,
    ),
)
INVALIDATE_VALIDATOR = _build_validator(RequestMethod.INVALIDATE.value)
LET_VALIDATOR = _build_validator(RequestMethod.LET.value, _list_schema(min_length=2))
UNSET_VALIDATOR = _build_validator(RequestMethod.UNSET.value, _list_schema())
LIVE_VALIDATOR = _build_validator(RequestMethod.LIVE.value, _list_schema())
KILL_VALIDATOR = _build_validator(RequestMethod.KILL.value, _list_schema())
QUERY_VALIDATOR = _build_validator(
    RequestMethod.QUERY.value, _list_schema(min_length=2, max_length=2)
)
INSERT_VALIDATOR = _build_validator(
    RequestMethod.INSERT.value, _list_schema(min_length=2, max_length=2)
)
PATCH_VALIDATOR = _build_validator(
    RequestMethod.PATCH.value, _list_schema(min_length=2, max_length=2)
)
SELECT_VALIDATOR = _build_validator(RequestMethod.SELECT.value, _list_schema())
CREATE_VALIDATOR = _build_validator(
    RequestMethod.CREATE.value, _list_schema(min_length=1, max_length=2)
)
UPDATE_VALIDATOR = _build_validator(
    RequestMethod.UPDATE.value, _list_schema(min_length=1, max_length=2)
)
MERGE_VALIDATOR = _build_validator(
    RequestMethod.MERGE.value, _list_schema(min_length=1, max_length=2)
)
DELETE_VALIDATOR = _build_validator(
    RequestMethod.DELETE.value, _list_schema(min_length=1, max_length=1)
)
INSERT_RELATION_VALIDATOR = _build_validator(
    RequestMethod.INSERT_RELATION.value, _list_schema(min_length=2, max_length=2)
)
UPSERT_VALIDATOR = _build_validator(
    RequestMethod.UPSERT.value, _list_schema(min_length=1, max_length=2)
)

_VALIDATORS: dict[RequestMethod, SchemaValidator] = {
    RequestMethod.USE: USE_VALIDATOR,
    RequestMethod.INFO: INFO_VALIDATOR,
    RequestMethod.VERSION: VERSION_VALIDATOR,
    RequestMethod.AUTHENTICATE: AUTHENTICATE_VALIDATOR,
    RequestMethod.INVALIDATE: INVALIDATE_VALIDATOR,
    RequestMethod.LET: LET_VALIDATOR,
    RequestMethod.UNSET: UNSET_VALIDATOR,
    RequestMethod.LIVE: LIVE_VALIDATOR,
    RequestMethod.KILL: KILL_VALIDATOR,
    RequestMethod.QUERY: QUERY_VALIDATOR,
    RequestMethod.INSERT: INSERT_VALIDATOR,
    RequestMethod.PATCH: PATCH_VALIDATOR,
    RequestMethod.SELECT: SELECT_VALIDATOR,
    RequestMethod.CREATE: CREATE_VALIDATOR,
    RequestMethod.UPDATE: UPDATE_VALIDATOR,
    RequestMethod.MERGE: MERGE_VALIDATOR,
    RequestMethod.DELETE: DELETE_VALIDATOR,
    RequestMethod.INSERT_RELATION: INSERT_RELATION_VALIDATOR,
    RequestMethod.UPSERT: UPSERT_VALIDATOR,
}


def _validate_payload(data: dict[str, Any], method: RequestMethod) -> None:
    validator = _VALIDATORS.get(method)
    if validator is None:
        return
    try:
        validator.validate_python(data)
    except PydanticValidationError as exc:
        errors = _format_errors(exc)
        raise ValueError(
            f"Invalid schema for Cbor WS encoding for {method.value}: {errors}"
        ) from None


_AUTH_KEY_MAP = {
    "namespace": "ns",
    "NS": "ns",
    "database": "db",
    "DB": "db",
    "access": "ac",
    "AC": "ac",
    "username": "user",
    "password": "pass",
}


def _build_auth_params(vars_dict: dict[str, Any]) -> dict[str, Any]:
    """Build wire-format auth params from user vars (supports bearer, refresh, record)."""
    wire: dict[str, Any] = {}
    for k in (
        "namespace",
        "NS",
        "database",
        "DB",
        "access",
        "AC",
        "username",
        "password",
        "user",
        "pass",
        "key",
        "refresh",
    ):
        if k in vars_dict and vars_dict[k] is not None:
            wire[_AUTH_KEY_MAP.get(k, k)] = vars_dict[k]
    if "variables" in vars_dict and isinstance(vars_dict.get("variables"), dict):
        for k, v in vars_dict["variables"].items():
            if v is None:
                continue
            wire[_AUTH_KEY_MAP.get(k, k)] = v
    return {k: v for k, v in wire.items() if v is not None}


class WsCborDescriptor:
    def __get__(self, obj: RequestMessage, type: Any = None) -> bytes:
        if obj.method == RequestMethod.USE:
            return self.prep_use(obj)
        elif obj.method == RequestMethod.INFO:
            return self.prep_info(obj)
        elif obj.method == RequestMethod.VERSION:
            return self.prep_version(obj)
        elif obj.method == RequestMethod.SIGN_UP:
            return self.prep_signup(obj)
        elif obj.method == RequestMethod.SIGN_IN:
            return self.prep_signin(obj)
        elif obj.method == RequestMethod.AUTHENTICATE:
            return self.prep_authenticate(obj)
        elif obj.method == RequestMethod.INVALIDATE:
            return self.prep_invalidate(obj)
        elif obj.method == RequestMethod.LET:
            return self.prep_let(obj)
        elif obj.method == RequestMethod.UNSET:
            return self.prep_unset(obj)
        elif obj.method == RequestMethod.LIVE:
            return self.prep_live(obj)
        elif obj.method == RequestMethod.KILL:
            return self.prep_kill(obj)
        elif obj.method == RequestMethod.QUERY:
            return self.prep_query(obj)
        elif obj.method == RequestMethod.INSERT:
            return self.prep_insert(obj)
        elif obj.method == RequestMethod.PATCH:
            return self.prep_patch(obj)
        elif obj.method == RequestMethod.SELECT:
            return self.prep_select(obj)
        elif obj.method == RequestMethod.CREATE:
            return self.prep_create(obj)
        elif obj.method == RequestMethod.UPDATE:
            return self.prep_update(obj)
        elif obj.method == RequestMethod.MERGE:
            return self.prep_merge(obj)
        elif obj.method == RequestMethod.DELETE:
            return self.prep_delete(obj)
        elif obj.method == RequestMethod.INSERT_RELATION:
            return self.prep_insert_relation(obj)
        elif obj.method == RequestMethod.UPSERT:
            return self.prep_upsert(obj)
        elif obj.method == RequestMethod.ATTACH:
            return self.prep_attach(obj)
        elif obj.method == RequestMethod.DETACH:
            return self.prep_detach(obj)
        elif obj.method == RequestMethod.BEGIN:
            return self.prep_begin(obj)
        elif obj.method == RequestMethod.COMMIT:
            return self.prep_commit(obj)
        elif obj.method == RequestMethod.CANCEL:
            return self.prep_cancel(obj)

        raise ValueError(f"Invalid method for Cbor WS encoding: {obj.method}")

    def prep_use(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("namespace"), obj.kwargs.get("database")],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_info(self, obj: RequestMessage) -> bytes:
        data = {"id": obj.id, "method": obj.method.value}
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_version(self, obj: RequestMessage) -> bytes:
        data = {"id": obj.id, "method": obj.method.value}
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_signup(self, obj: RequestMessage) -> bytes:
        passed_params = cast(dict[str, Any], obj.kwargs.get("data"))
        if not passed_params:
            raise ValueError(
                "Signup requires a data dict (namespace, database, access, variables or user/pass)"
            )
        params_dict = _build_auth_params(passed_params)
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [params_dict],
        }
        _inject_session_txn(data, obj)
        return encode(data)

    def prep_signin(self, obj: RequestMessage) -> bytes:
        params = obj.kwargs.get("params")
        if params is None or not isinstance(params, dict):
            raise ValueError(
                "Signin requires a params dict (e.g. username/password, key, or refresh)"
            )
        params_dict = _build_auth_params(params)
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [params_dict],
        }
        _inject_session_txn(data, obj)
        return encode(data)

    def prep_authenticate(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("token")],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_invalidate(self, obj: RequestMessage) -> bytes:
        data = {"id": obj.id, "method": obj.method.value}
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_let(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("key"), obj.kwargs.get("value")],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_unset(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": obj.kwargs.get("params"),
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_live(self, obj: RequestMessage) -> bytes:
        table = obj.kwargs.get("table")
        if isinstance(table, str):
            table = Table(table)
        data = {"id": obj.id, "method": obj.method.value, "params": [table]}
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_kill(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("uuid")],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_query(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("query"), obj.kwargs.get("params", dict())],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_insert(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_record(cast(RecordIdType, obj.kwargs.get("collection"))),
                obj.kwargs.get("params"),
            ],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_patch(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_record(cast(RecordIdType, obj.kwargs.get("collection"))),
                obj.kwargs.get("params"),
            ],
        }
        if obj.kwargs.get("params") is None:
            raise ValueError("parameters cannot be None for a patch method")
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_select(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": obj.kwargs.get("params"),
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_create(self, obj: RequestMessage) -> bytes:
        params: list[Any] = [
            process_record(cast(RecordIdType, obj.kwargs.get("collection")))
        ]
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": params,
        }
        if obj.kwargs.get("data"):
            params.append(obj.kwargs.get("data"))

        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_update(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_record(cast(RecordIdType, obj.kwargs.get("record_id"))),
                obj.kwargs.get("data", dict()),
            ],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_merge(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_record(cast(RecordIdType, obj.kwargs.get("record_id"))),
                obj.kwargs.get("data", dict()),
            ],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_delete(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [process_record(cast(RecordIdType, obj.kwargs.get("record_id")))],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_insert_relation(self, obj: RequestMessage) -> bytes:
        params_list: list[Any] = [Table(cast(str, obj.kwargs.get("table")))]
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": params_list,
        }
        params = obj.kwargs.get("params", [])
        params_list.append(params)

        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_upsert(self, obj: RequestMessage) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_record(cast(RecordIdType, obj.kwargs.get("record_id"))),
                obj.kwargs.get("data", dict()),
            ],
        }
        _inject_session_txn(data, obj)
        _validate_payload(data, obj.method)
        return encode(data)

    def prep_attach(self, obj: RequestMessage) -> bytes:
        session = obj.kwargs.get("session")
        if session is None:
            raise ValueError("attach requires session (uuid.UUID)")
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "session": str(session) if isinstance(session, UUID) else session,
        }
        return encode(data)

    def prep_detach(self, obj: RequestMessage) -> bytes:
        session = obj.kwargs.get("session")
        if session is None:
            raise ValueError("detach requires session (uuid.UUID)")
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "session": str(session) if isinstance(session, UUID) else session,
        }
        return encode(data)

    def prep_begin(self, obj: RequestMessage) -> bytes:
        data = {"id": obj.id, "method": obj.method.value}
        _inject_session_txn(data, obj)
        return encode(data)

    def prep_commit(self, obj: RequestMessage) -> bytes:
        txn = obj.kwargs.get("txn")
        if txn is None:
            raise ValueError("commit requires txn (uuid.UUID)")
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [str(txn) if isinstance(txn, UUID) else txn],
        }
        session = obj.kwargs.get("session")
        if session is not None:
            data["session"] = str(session) if isinstance(session, UUID) else session
        return encode(data)

    def prep_cancel(self, obj: RequestMessage) -> bytes:
        txn = obj.kwargs.get("txn")
        if txn is None:
            raise ValueError("cancel requires txn (uuid.UUID)")
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [str(txn) if isinstance(txn, UUID) else txn],
        }
        session = obj.kwargs.get("session")
        if session is not None:
            data["session"] = str(session) if isinstance(session, UUID) else session
        return encode(data)
