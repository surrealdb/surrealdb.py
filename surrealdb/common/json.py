"""
Copyright © SurrealDB Ltd

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
from typing import Any
from typing import Union


try:
    import orjson as jsonlib
except ImportError:
    import json as jsonlib

__all__ = (
    "dumps",
    "loads",
)


def dumps(obj: Any, **kwargs: Any) -> str:
    result = jsonlib.dumps(obj, **kwargs)
    if isinstance(result, bytes):
        result = result.decode("utf-8")

    return result


def loads(content: Union[bytes, str], **kwargs: Any) -> Any:
    return jsonlib.loads(content, **kwargs)
