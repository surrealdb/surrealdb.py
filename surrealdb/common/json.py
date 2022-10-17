"""
Copyright © SurrealDB Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from typing import Any, Iterable
from typing import Union


try:
    import orjson as jsonlib
except ImportError:
    import json as jsonlib

__all__ = (
    "dumps",
    "loads",
)


def dumps(obj: Any) -> str:
    """Serialize an object to a SurrealDB string."""
    if any(isinstance(obj, t) for t in [int, float]):
        return repr(obj)
    elif isinstance(obj, str):
        return f'"{obj}"'
    elif hasattr(obj, "id"):
        return obj.id
    elif isinstance(obj, dict):
        if obj.get("id") is not None:
            return obj["id"]
        return "{" + ", ".join(f"{k}: {dumps(v)}" for k, v in obj.items()) + "}"
    elif isinstance(obj, Iterable):
        return f'[{", ".join(dumps(v) for v in obj)}]'
    raise Exception(f"Object is not json serializable: {repr(obj)}")


def loads(content: Union[bytes, str], **kwargs: Any) -> Any:
    """Deserialize a JSON string to an object."""
    return jsonlib.loads(content, **kwargs)
