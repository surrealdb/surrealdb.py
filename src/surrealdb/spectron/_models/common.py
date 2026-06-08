from __future__ import annotations

import dataclasses
import enum
import types
import typing
from typing import Any, ClassVar, TypeVar, get_args, get_origin

_UNION_ORIGINS: tuple[Any, ...] = (typing.Union, types.UnionType)

T = TypeVar("T", bound="Model")


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)


def _wire_name(f: dataclasses.Field[Any]) -> str:
    override = f.metadata.get("json") if f.metadata else None
    if isinstance(override, str) and override:
        return override
    return _to_camel(f.name)


class Model:
    __resolved_hints__: ClassVar[dict[str, Any]] = {}

    @classmethod
    def _hints(cls) -> dict[str, Any]:
        cached = cls.__dict__.get("__resolved_hints__")
        if cached is None:
            cached = typing.get_type_hints(cls)
            cls.__resolved_hints__ = cached
        return cached

    @classmethod
    def from_dict(cls: type[T], data: Any) -> T:
        if data is None or not isinstance(data, dict):
            raise TypeError(f"Cannot decode {cls.__name__} from {type(data).__name__}")
        hints = cls._hints()
        kwargs: dict[str, Any] = {}
        for f in dataclasses.fields(cls):  # type: ignore[arg-type]
            wire_key = _wire_name(f)
            field_type = hints.get(f.name, f.type)
            has_default = (
                f.default is not dataclasses.MISSING
                or f.default_factory is not dataclasses.MISSING
            )
            if wire_key in data:
                raw = data[wire_key]
            elif f.name in data:
                raw = data[f.name]
            elif not has_default:
                raise ValueError(
                    f"Missing required field '{wire_key}' for {cls.__name__}"
                )
            else:
                continue
            kwargs[f.name] = _decode(field_type, raw)
        return cls(**kwargs)

    def to_dict(self, *, omit_none: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in dataclasses.fields(self):  # type: ignore[arg-type]
            value = getattr(self, f.name)
            if value is None and omit_none:
                continue
            out[_wire_name(f)] = _encode(value)
        return out


def _decode(type_hint: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(type_hint)
    if origin in _UNION_ORIGINS:
        args = [a for a in get_args(type_hint) if a is not type(None)]
        if not args:
            return value
        for candidate in args:
            try:
                return _decode(candidate, value)
            except (TypeError, ValueError):
                continue
        return value
    if origin in (list, tuple):
        if not isinstance(value, (list, tuple)):
            return value
        inner_args = get_args(type_hint)
        inner = inner_args[0] if inner_args else Any
        return [_decode(inner, v) for v in value]
    if origin is dict:
        if not isinstance(value, dict):
            return value
        dict_args = get_args(type_hint)
        v_type = dict_args[1] if len(dict_args) == 2 else Any
        return {k: _decode(v_type, v) for k, v in value.items()}
    if isinstance(type_hint, type):
        if issubclass(type_hint, Model) and isinstance(value, dict):
            return type_hint.from_dict(value)
        if issubclass(type_hint, enum.Enum):
            try:
                return type_hint(value)
            except ValueError:
                return value
    return value


def _encode(value: Any) -> Any:
    if isinstance(value, Model):
        return value.to_dict()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    return value


__all__ = ["Model", "_decode", "_encode", "_to_camel", "_wire_name"]
