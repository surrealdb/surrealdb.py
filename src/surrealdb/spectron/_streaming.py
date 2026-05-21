from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import aiohttp
    import requests


@dataclass(frozen=True)
class ChatChunk:
    delta: str = ""
    trace_id: str | None = None
    session_id: str | None = None
    done: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


def _frame(event: str | None, payload: str) -> ChatChunk:
    if payload == "[DONE]":
        return ChatChunk(done=True)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ChatChunk(delta=payload)
    if not isinstance(data, dict):
        return ChatChunk(delta=str(data))
    trace_id = data.get("traceId") or data.get("trace_id")
    session_id = data.get("sessionId") or data.get("session_id")
    if event == "done" or data.get("done"):
        return ChatChunk(
            done=True,
            trace_id=trace_id,
            session_id=session_id,
            raw=data,
        )
    return ChatChunk(
        delta=data.get("delta", "") or data.get("token", "") or "",
        trace_id=trace_id,
        session_id=session_id,
        raw=data,
    )


def _decode_line(raw: bytes | str) -> str:
    if isinstance(raw, bytes):
        try:
            return raw.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace").rstrip("\r\n")
    return raw.rstrip("\r\n")


def _consume(line: str, state: dict[str, Any]) -> ChatChunk | None:
    if line == "":
        if state["data_lines"]:
            payload = "\n".join(state["data_lines"])
            chunk = _frame(state["event"], payload)
            state["event"] = None
            state["data_lines"] = []
            return chunk
        state["event"] = None
        state["data_lines"] = []
        return None
    if line.startswith(":"):
        return None
    if line.startswith("event:"):
        state["event"] = line[len("event:") :].strip()
    elif line.startswith("data:"):
        state["data_lines"].append(line[len("data:") :].lstrip(" "))
    return None


def iter_sse_blocking(response: "requests.Response") -> Iterator[ChatChunk]:
    state: dict[str, Any] = {"event": None, "data_lines": []}
    try:
        for raw_line in response.iter_lines(decode_unicode=False):
            if raw_line is None:
                continue
            line = _decode_line(raw_line) if raw_line else ""
            chunk = _consume(line, state)
            if chunk is not None:
                yield chunk
        if state["data_lines"]:
            yield _frame(state["event"], "\n".join(state["data_lines"]))
    finally:
        response.close()


async def iter_sse_async(response: "aiohttp.ClientResponse") -> AsyncIterator[ChatChunk]:
    state: dict[str, Any] = {"event": None, "data_lines": []}
    try:
        async for raw_line in response.content:
            line = _decode_line(raw_line)
            chunk = _consume(line, state)
            if chunk is not None:
                yield chunk
        if state["data_lines"]:
            yield _frame(state["event"], "\n".join(state["data_lines"]))
    finally:
        response.release()


__all__ = ["ChatChunk", "iter_sse_blocking", "iter_sse_async"]
