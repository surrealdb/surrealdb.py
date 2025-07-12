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
        # Check if using new params format
        if "params" in obj.kwargs:
            # New API: params are stored in obj.kwargs["params"]
            use_params = obj.kwargs["params"]  # [namespace, database]
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": use_params,
            }
        else:
            # Old API: namespace and database are stored directly in kwargs
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
        # Check if using new params format
        if "params" in obj.kwargs:
            # New API: params are stored in obj.kwargs["params"]
            signin_data = obj.kwargs["params"][0]  # First (and only) item in params list
            
            # Transform field names for SurrealDB compatibility
            transformed_data = {}
            for key, value in signin_data.items():
                if key == "username":
                    transformed_data["user"] = value
                elif key == "password":
                    transformed_data["pass"] = value
                else:
                    transformed_data[key] = value
            
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [transformed_data],
            }
        else:
            # Old API: params are stored directly in kwargs
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
        # Check if using new params format
        if "params" in obj.kwargs:
            # New API: params are stored in obj.kwargs["params"]
            token = obj.kwargs["params"][0]  # First (and only) item in params list
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [token],
            }
        else:
            # Old API: token is stored directly in kwargs
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
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            let_params = obj.kwargs["params"]  # [key, value]
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": let_params,
            }
        else:
            # Old API: key and value are stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [obj.kwargs.get("key"), obj.kwargs.get("value")],
            }
        return encode(data)

    def prep_unset(self, obj) -> bytes:
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            unset_params = obj.kwargs["params"]  # [key]
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": unset_params,
            }
        else:
            # Old API: params are stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": obj.kwargs.get("params"),
            }
        return encode(data)

    def prep_live(self, obj) -> bytes:
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            live_params = obj.kwargs["params"]  # [table]
            # Process the first parameter (table) if it's a string
            if len(live_params) > 0 and isinstance(live_params[0], str):
                live_params[0] = Table(live_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": live_params,
            }
        else:
            # Old API: table is stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [Table(obj.kwargs.get("table"))],
            }
        return encode(data)

    def prep_kill(self, obj) -> bytes:
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            kill_params = obj.kwargs["params"]  # [uuid]
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": kill_params,
            }
        else:
            # Old API: uuid is stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [obj.kwargs.get("uuid")],
            }
        return encode(data)

    def prep_query(self, obj) -> bytes:
        # Check if using new params format
        if "params" in obj.kwargs:
            # New API: params are stored in obj.kwargs["params"]
            query_params = obj.kwargs["params"]  # [query, vars]
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": query_params,
            }
        else:
            # Old API: query and params are stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [obj.kwargs.get("query"), obj.kwargs.get("params", dict())],
            }
        return encode(data)

    def prep_insert(self, obj) -> bytes:
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            insert_params = obj.kwargs["params"]  # [table, data]
            # Process the first parameter (table) if it's a string
            if len(insert_params) > 0 and isinstance(insert_params[0], str):
                insert_params[0] = process_thing(insert_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": insert_params,
            }
        else:
            # Old API: collection and params are stored directly in kwargs
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
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            patch_params = obj.kwargs["params"]  # [thing, data]
            # Process the first parameter (thing) if it's a string
            if len(patch_params) > 0 and isinstance(patch_params[0], str):
                patch_params[0] = process_thing(patch_params[0])
            if len(patch_params) < 2 or patch_params[1] is None:
                raise ValueError("parameters cannot be None for a patch method")
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": patch_params,
            }
        else:
            # Old API: collection and params are stored directly in kwargs
            if obj.kwargs.get("params") is None:
                raise ValueError("parameters cannot be None for a patch method")
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    process_thing(obj.kwargs.get("collection")),
                    obj.kwargs.get("params"),
                ],
            }
        return encode(data)

    def prep_select(self, obj) -> bytes:
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            select_params = obj.kwargs["params"]  # [thing]
            # Process the first parameter (thing) if it's a string
            if len(select_params) > 0 and isinstance(select_params[0], str):
                select_params[0] = process_thing(select_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": select_params,
            }
        else:
            # Old API: params are stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": obj.kwargs.get("params"),
            }
        return encode(data)

    def prep_create(self, obj) -> bytes:
        # Check if using new params format
        if "params" in obj.kwargs:
            # New API: params are stored in obj.kwargs["params"]
            create_params = obj.kwargs["params"]  # [thing, data?]
            # Process the first parameter (thing) if it's a string
            if len(create_params) > 0 and isinstance(create_params[0], str):
                create_params[0] = process_thing(create_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": create_params,
            }
        else:
            # Old API: collection and data are stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [process_thing(obj.kwargs.get("collection"))],
            }
            if obj.kwargs.get("data"):
                data["params"].append(obj.kwargs.get("data"))
        return encode(data)

    def prep_update(self, obj) -> bytes:
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            update_params = obj.kwargs["params"]  # [thing, data?]
            # Process the first parameter (thing) if it's a string
            if len(update_params) > 0 and isinstance(update_params[0], str):
                update_params[0] = process_thing(update_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": update_params,
            }
        else:
            # Old API: record_id and data are stored directly in kwargs
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
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            merge_params = obj.kwargs["params"]  # [thing, data?]
            # Process the first parameter (thing) if it's a string
            if len(merge_params) > 0 and isinstance(merge_params[0], str):
                merge_params[0] = process_thing(merge_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": merge_params,
            }
        else:
            # Old API: record_id and data are stored directly in kwargs
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
        # Check if using new params format
        if "params" in obj.kwargs:
            # New API: params are stored in obj.kwargs["params"]
            delete_params = obj.kwargs["params"]  # [thing]
            # Process the first parameter (thing) if it's a string
            if len(delete_params) > 0 and isinstance(delete_params[0], str):
                delete_params[0] = process_thing(delete_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": delete_params,
            }
        else:
            # Old API: record_id is stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [process_thing(obj.kwargs.get("record_id"))],
            }
        return encode(data)

    def prep_insert_relation(self, obj) -> bytes:
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            insert_relation_params = obj.kwargs["params"]  # [table, data]
            # Process the first parameter (table) if it's a string
            if len(insert_relation_params) > 0 and isinstance(insert_relation_params[0], str):
                insert_relation_params[0] = Table(insert_relation_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": insert_relation_params,
            }
        else:
            # Old API: table and params are stored directly in kwargs
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
        # Check if using new params format (params is a list)
        if "params" in obj.kwargs and isinstance(obj.kwargs["params"], list):
            # New API: params are stored in obj.kwargs["params"] as a list
            upsert_params = obj.kwargs["params"]  # [thing, data?]
            # Process the first parameter (thing) if it's a string
            if len(upsert_params) > 0 and isinstance(upsert_params[0], str):
                upsert_params[0] = process_thing(upsert_params[0])
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": upsert_params,
            }
        else:
            # Old API: record_id and data are stored directly in kwargs
            data = {
                "id": obj.id,
                "method": obj.method.value,
                "params": [
                    process_thing(obj.kwargs.get("record_id")),
                    obj.kwargs.get("data", dict()),
                ],
            }
        return encode(data)
