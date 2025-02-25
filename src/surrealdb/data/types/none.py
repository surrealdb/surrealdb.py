"""Defines the class for None types so they can be serialized in cbor. Check the gottas section at the bottom of the main readme for details"""
from typing import Any, Optional


class NoneType:
    """
    A None type that can be serialized in cbor
    """
    @staticmethod
    def parse_value(value: Optional[Any]) -> Any:
        if value is None:
            return NoneType()
        return value


def replace_none(obj: Any) -> Any:
    """
    Recursively replace None values with NoneType instances in any structure.
    Args:
        obj: The object to be scanned for None types
    returns:
        the same object but will all None types replaced for NonType objects
    """
    if obj is None:
        return NoneType()
    elif isinstance(obj, dict):
        return {key: replace_none(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [replace_none(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(replace_none(item) for item in obj)
    elif isinstance(obj, set):
        return {replace_none(item) for item in obj}
    else:
        return obj
