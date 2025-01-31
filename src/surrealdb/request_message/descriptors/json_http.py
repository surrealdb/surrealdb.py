from marshmallow import ValidationError
from surrealdb.request_message.methods import RequestMethod
from marshmallow import Schema, fields
from typing import Tuple
from enum import Enum
import json


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class JsonHttpDescriptor:
    def __get__(self, obj, type=None) -> Tuple[str, HttpMethod, str]:
        if obj.method == RequestMethod.SIGN_IN:
            return self.prep_signin(obj)
        # if obj.method == RequestMethod.USE:
        #     return self.prep_use(obj)
        # elif obj.method == RequestMethod.INFO:
        #     return self.prep_info(obj)
        # elif obj.method == RequestMethod.VERSION:
        #     return self.prep_version(obj)
        # elif obj.method == RequestMethod.SIGN_UP:
        #     return self.prep_signup(obj)
        # elif obj.method == RequestMethod.SIGN_IN:
        #     return self.prep_signin(obj)
        # elif obj.method == RequestMethod.AUTHENTICATE:
        #     return self.prep_authenticate(obj)
        # elif obj.method == RequestMethod.INVALIDATE:
        #     return self.prep_invalidate(obj)
        # elif obj.method == RequestMethod.LET:
        #     return self.prep_let(obj)
        # elif obj.method == RequestMethod.UNSET:
        #     return self.prep_unset(obj)
        # elif obj.method == RequestMethod.LIVE:
        #     return self.prep_live(obj)
        # elif obj.method == RequestMethod.KILL:
        #     return self.prep_kill(obj)
        # elif obj.method == RequestMethod.QUERY:
        #     return self.prep_query(obj)
        # elif obj.method == RequestMethod.INSERT:
        #     return self.prep_insert(obj)
        # elif obj.method == RequestMethod.PATCH:
        #     return self.prep_patch(obj)

    @staticmethod
    def serialize(data: dict, schema: Schema, context: str) -> str:
        try:
            result = schema.load(data)
        except ValidationError as err:
            raise ValidationError(f"Validation error for {context}:", err.messages)
        return json.dumps(schema.dump(result))


    def prep_signin(self, obj) -> Tuple[str, HttpMethod, str]:
        class SignInSchema(Schema):
            ns = fields.Str(required=False)  # Optional Namespace
            db = fields.Str(required=False)  # Optional Database
            ac = fields.Str(required=False)  # Optional Account category
            user = fields.Str(required=True)  # Required Username
            pass_ = fields.Str(required=True, data_key="pass")  # Required Password

        schema = SignInSchema()

        if obj.kwargs.get("namespace") is None:
            # root user signing in
            data = {
                "user": obj.kwargs.get("username"),
                "pass": obj.kwargs.get("password")
            }
        else:
            data = {
                "ns": obj.kwargs.get("namespace"),
                "db": obj.kwargs.get("database"),
                "ac": obj.kwargs.get("account"),
                "user": obj.kwargs.get("username"),
                "pass": obj.kwargs.get("password")
            }

        result = self.serialize(data, schema, "HTTP signin")
        return result, HttpMethod.POST, "signin"
