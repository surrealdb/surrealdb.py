from enum import Enum


class RequestMethod(Enum):
    USE = "use"
    SIGN_IN = "signin"
    SIGN_UP = "signup"
    INFO = "info"
    VERSION = "version"
    AUTHENTICATE = "authenticate"
    INVALIDATE = "invalidate"
    LET = "let"
    UNSET = "unset"
    SELECT = "select"
    QUERY = "query"
    CREATE = "create"
    INSERT = "insert"
    INSERT_RELATION = "insert_relation"
    PATCH = "patch"
    MERGE = "merge"
    UPDATE = "update"
    UPSERT = "upsert"
    DELETE = "delete"
    LIVE = "live"
    KILL = "kill"
    POST = "post"

    @staticmethod
    def from_string(method: str) -> "RequestMethod":
        return RequestMethod(method.lower())
