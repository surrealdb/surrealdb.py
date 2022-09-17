from __future__ import annotations

from typing import Any


try:
    import orjson as jsonlib
except ImportError:
    import json as jsonlib


def dumps(obj: Any, **kwargs: Any) -> str:
    result = jsonlib.dumps(obj, **kwargs)
    if isinstance(result, bytes):
        result = result.decode("utf-8")

    return result


def loads(content: bytes | str, **kwargs: Any) -> Any:
    return jsonlib.loads(content, **kwargs)
