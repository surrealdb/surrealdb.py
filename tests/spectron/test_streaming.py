from __future__ import annotations

from surrealdb.spectron import ChatChunk
from surrealdb.spectron._streaming import _consume, _frame


def _drain(lines: list[str]) -> list[ChatChunk]:
    state: dict[str, object] = {"event": None, "data_lines": []}
    out: list[ChatChunk] = []
    for line in lines:
        chunk = _consume(line, state)
        if chunk is not None:
            out.append(chunk)
    if state["data_lines"]:  # type: ignore[arg-type]
        out.append(_frame(state["event"], "\n".join(state["data_lines"])))  # type: ignore[arg-type]
    return out


def test_parses_delta_chunks():
    chunks = _drain(
        [
            'data: {"delta": "Hello"}',
            "",
            'data: {"delta": " world"}',
            "",
            "data: [DONE]",
            "",
        ]
    )
    assert [c.delta for c in chunks[:2]] == ["Hello", " world"]
    assert chunks[-1].done is True


def test_parses_event_done_with_trace_and_session():
    chunks = _drain(
        [
            "event: done",
            'data: {"traceId": "tr:1", "sessionId": "s:1", "reply": "ok"}',
            "",
        ]
    )
    assert len(chunks) == 1
    assert chunks[0].done is True
    assert chunks[0].trace_id == "tr:1"
    assert chunks[0].session_id == "s:1"
    assert chunks[0].raw["reply"] == "ok"


def test_data_carrying_done_flag_is_terminal():
    chunks = _drain(['data: {"done": true, "traceId": "tr"}', ""])
    assert chunks[0].done is True
    assert chunks[0].trace_id == "tr"


def test_non_json_payload_falls_back_to_delta():
    chunks = _drain(["data: just text", ""])
    assert len(chunks) == 1
    assert chunks[0].delta == "just text"


def test_comment_lines_are_ignored():
    chunks = _drain([": this is a comment", 'data: {"delta": "hi"}', ""])
    assert len(chunks) == 1
    assert chunks[0].delta == "hi"


def test_multi_line_data_is_joined():
    chunks = _drain(['data: {"delta":', 'data:  "split"}', ""])
    assert chunks[0].delta == "split"
