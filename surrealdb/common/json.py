from typing import Union
from typing import Any


try:
    import orjson as jsonlib
except ImportError:
    import json as jsonlib

__all__ = ["dumps", "loads"]


def dumps(obj: Any, **kwargs: Any) -> str:
    result = jsonlib.dumps(obj, **kwargs)
    if isinstance(result, bytes):
        result = result.decode("utf-8")

    return result


def loads(content: Union[bytes, str], **kwargs: Any) -> Any:
    return jsonlib.loads(content, **kwargs)
