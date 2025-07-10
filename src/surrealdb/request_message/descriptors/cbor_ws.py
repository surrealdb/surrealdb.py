from surrealdb.data.cbor import encode
from surrealdb.data.types.table import Table
from surrealdb.data.utils import process_thing
from surrealdb.request_message.methods import RequestMethod


class WsCborDescriptor:
    """
    CBOR WebSocket Descriptor - Pure Encoding Layer

    This class handles CBOR encoding for WebSocket messages.
    Validation is now handled by ValidatedRequestMessage using Pydantic schemas.
    """

    def __get__(self, obj, type=None) -> bytes:
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

        raise ValueError(f"Invalid method for Cbor WS encoding: {obj.method}")

    def prep_use(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("namespace"), obj.kwargs.get("database")],
        }
        return encode(data)

    def prep_info(self, obj) -> bytes:
        data = {"id": obj.id, "method": obj.method.value}
        return encode(data)

    def prep_version(self, obj) -> bytes:
        data = {"id": obj.id, "method": obj.method.value}
        return encode(data)

    def prep_signup(self, obj) -> bytes:
        passed_params = obj.kwargs.get("data")
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                {
                    "NS": passed_params.get("namespace"),
                    "DB": passed_params.get("database"),
                    "AC": passed_params.get("access"),
                }
            ],
        }
        for key, value in passed_params["variables"].items():
            data["params"][0][key] = value
        return encode(data)

    def prep_signin(self, obj) -> bytes:
        """
        Handle different signin patterns:
        - user+pass -> done
        - user+pass+ac -> done
        - user+pass+ns -> done
        - user+pass+ns+ac -> done
        - user+pass+ns+db
        - user+pass+ns+db+ac
        - ns+db+ac+any other vars
        """
        if obj.kwargs.get("namespace") is None:
            # root user signing in
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    {
                        "user": obj.kwargs.get("username"),
                        "pass": obj.kwargs.get("password"),
                    }
                ],
            }
        elif (
            obj.kwargs.get("namespace") is None and obj.kwargs.get("access") is not None
        ):
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    {
                        "ac": obj.kwargs.get("access"),
                        "user": obj.kwargs.get("username"),
                        "pass": obj.kwargs.get("password"),
                    }
                ],
            }
        elif obj.kwargs.get("database") is None and obj.kwargs.get("access") is None:
            # namespace signin
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    {
                        "ns": obj.kwargs.get("namespace"),
                        "user": obj.kwargs.get("username"),
                        "pass": obj.kwargs.get("password"),
                    }
                ],
            }
        elif (
            obj.kwargs.get("database") is None and obj.kwargs.get("access") is not None
        ):
            # access signin
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    {
                        "ns": obj.kwargs.get("namespace"),
                        "ac": obj.kwargs.get("access"),
                        "user": obj.kwargs.get("username"),
                        "pass": obj.kwargs.get("password"),
                    }
                ],
            }
        elif (
            obj.kwargs.get("database") is not None
            and obj.kwargs.get("namespace") is not None
            and obj.kwargs.get("access") is not None
            and obj.kwargs.get("variables") is None
        ):
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    {
                        "ns": obj.kwargs.get("namespace"),
                        "db": obj.kwargs.get("database"),
                        "ac": obj.kwargs.get("access"),
                        "user": obj.kwargs.get("username"),
                        "pass": obj.kwargs.get("password"),
                    }
                ],
            }

        elif obj.kwargs.get("username") is None and obj.kwargs.get("password") is None:
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    {
                        "ns": obj.kwargs.get("namespace"),
                        "db": obj.kwargs.get("database"),
                        "ac": obj.kwargs.get("access"),
                    }
                ],
            }
            for key, value in obj.kwargs.get("variables", {}).items():
                data["params"][0][key] = value

        elif (
            obj.kwargs.get("database") is not None
            and obj.kwargs.get("namespace") is not None
            and obj.kwargs.get("access") is None
        ):
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    {
                        "ns": obj.kwargs.get("namespace"),
                        "db": obj.kwargs.get("database"),
                        "user": obj.kwargs.get("username"),
                        "pass": obj.kwargs.get("password"),
                    }
                ],
            }

        else:
            raise ValueError(f"Invalid data for signin: {obj.kwargs}")
        return encode(data)

    def prep_authenticate(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("token")],
        }
        return encode(data)

    def prep_invalidate(self, obj) -> bytes:
        data = {"id": obj.id, "method": obj.method.value}
        return encode(data)

    def prep_let(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("key"), obj.kwargs.get("value")],
        }
        return encode(data)

    def prep_unset(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": obj.kwargs.get("params"),
        }
        return encode(data)

    def prep_live(self, obj) -> bytes:
        table = obj.kwargs.get("table")
        if isinstance(table, str):
            table = Table(table)
        data = {"id": obj.id, "method": obj.method.value, "params": [table]}
        return encode(data)

    def prep_kill(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("uuid")],
        }
        return encode(data)

    def prep_query(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [obj.kwargs.get("query"), obj.kwargs.get("params", dict())],
        }
        return encode(data)

    def prep_insert(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_thing(obj.kwargs.get("collection")),
                obj.kwargs.get("params"),
            ],
        }
        return encode(data)

    def prep_patch(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_thing(obj.kwargs.get("collection")),
                obj.kwargs.get("params"),
            ],
        }
        if obj.kwargs.get("params") is None:
            raise ValueError("parameters cannot be None for a patch method")
        return encode(data)

    def prep_select(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": obj.kwargs.get("params"),
        }
        return encode(data)

    def prep_create(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [process_thing(obj.kwargs.get("collection"))],
        }
        if obj.kwargs.get("data"):
            data["params"].append(obj.kwargs.get("data"))
        return encode(data)

    def prep_update(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_thing(obj.kwargs.get("record_id")),
                obj.kwargs.get("data", dict()),
            ],
        }
        return encode(data)

    def prep_merge(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_thing(obj.kwargs.get("record_id")),
                obj.kwargs.get("data", dict()),
            ],
        }
        return encode(data)

    def prep_delete(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [process_thing(obj.kwargs.get("record_id"))],
        }
        return encode(data)

    def prep_insert_relation(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                Table(obj.kwargs.get("table")),
            ],
        }
        params = obj.kwargs.get("params", [])
        data["params"].append(params)
        return encode(data)

    def prep_upsert(self, obj) -> bytes:
        data = {
            "id": obj.id,
            "method": obj.method.value,
            "params": [
                process_thing(obj.kwargs.get("record_id")),
                obj.kwargs.get("data", dict()),
            ],
        }
        return encode(data)
