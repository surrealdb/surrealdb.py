# Spectron

Python client for [Spectron](https://github.com/surrealdb/spectron), bundled
with `surrealdb`.

```python
from surrealdb import Spectron

with Spectron(
    context="acme-prod",
    endpoint="https://api.spectron.example",
    api_key="sk-spec-...",
) as memory:
    memory.remember("I work at Acme as CTO")
    hits = memory.recall("what do I do at Acme")
    print(hits.hits)
```

## Install

```
pip install surrealdb
```

## Clients

```python
from surrealdb import Spectron, AsyncSpectron

with Spectron(context="acme-prod", endpoint="https://api.spectron.example", api_key="sk-...") as memory:
    memory.remember("I work at Acme as CTO")

async with AsyncSpectron(context="acme-prod", endpoint="https://api.spectron.example", api_key="sk-...") as memory:
    await memory.remember("I work at Acme as CTO")
```

`Spectron` uses `requests`. `AsyncSpectron` uses `aiohttp`. Same method names
on both; add `await` for the async one.

Both clients are pinned to one context and hit `/api/v1/{context}/...`.

### Constructor

| Arg | Default | |
|---|---|---|
| `context` | required | Context id, e.g. `"acme-prod"`. |
| `endpoint` | required | Full URL of the Spectron host, e.g. `"https://api.spectron.example"`. No default. |
| `api_key` | required | Bearer token, as a string. Sent as `Authorization: Bearer <key>`. |
| `timeout` | `30.0` | Seconds per request. |
| `max_retries` | `3` | Retries for GETs and idempotent writes. |
| `transport` | `None` | Inject your own for testing. |

Pass `api_key` as a string from wherever you keep secrets. The SDK never
reads environment variables.

## Surface

| Method | Endpoint |
| --- | --- |
| `remember(text, ...)` | `POST /api/v1/{context}/facts` |
| `remember_many(items, ...)` | `POST /api/v1/{context}/facts/batch` |
| `recall(query, ...)` | `POST /api/v1/{context}/query` |
| `forget(query, ...)` | `POST /api/v1/{context}/forget` |
| `chat(message, stream=…)` | `POST /api/v1/{context}/chat` (SSE if `stream=True`) |
| `documents.upload(path, ...)` | `POST /api/v1/{context}/documents` (multipart) |

### Remember

```python
memory.remember("I work at Acme as CTO")
memory.remember("Acme acquired Beta", session_id="sess:abc", scope={"org": "acme"})

memory.remember_many([
    {"role": "user", "content": "I just got promoted to CTO"},
    {"role": "assistant", "content": "Congratulations!"},
])
```

`remember` and `remember_many` set an `Idempotency-Key` header derived from
`sha256(method | path | body | 30s-bucket)`, so a retry inside the bucket
collapses onto the previous attempt server-side.

### Recall

```python
result = memory.recall("what role do I have at Acme", k=10, mode="hybrid")
for hit in result.hits:
    print(hit.score, hit.source, hit.text)
```

### Forget

```python
memory.forget("anything about my old job")
memory.forget("draft notes", purge=True)
```

### Chat

```python
reply = memory.chat("what's my role?")
print(reply.reply)

# Streaming (Server-Sent Events). Yields ChatChunk objects.
for chunk in memory.chat("what's my role?", stream=True):
    if chunk.delta:
        print(chunk.delta, end="", flush=True)
    if chunk.done:
        print("\n[trace]", chunk.trace_id)
```

Async streaming:

```python
stream = await memory.chat("what's my role?", stream=True)
async for chunk in stream:
    ...
```

### Documents

```python
result = memory.documents.upload("returns.pdf", content_type="application/pdf")
print(result.id, result.status)
```

`path` accepts a filesystem path, bytes, or a file-like object.

## Errors

```python
from surrealdb import SpectronAPIError, SpectronNotFoundError

try:
    memory.recall("...")
except SpectronNotFoundError as exc:
    print(exc.status_code, exc.message)
except SpectronAPIError as exc:
    print(exc.status_code, exc.message, exc.trace_id)
```

| Exception | HTTP |
|---|---|
| `SpectronError` | base |
| `SpectronAPIError` | any non-2xx without a more specific class |
| `SpectronAuthError` | 401 |
| `SpectronScopeError` | 403 |
| `SpectronNotFoundError` | 404 |

Every `SpectronAPIError` carries `status_code`, `message`, `trace_id`, and
the decoded `body`.

## Retries and timeouts

- `GET` and idempotent writes (`remember`, `remember_many`) retry on
  connection errors and 5xx: 250ms, 500ms, 1s. Up to `max_retries`
  (default 3).
- Non-idempotent writes never retry. You handle it.
- Default timeout is 30s. Override with `timeout=` on the constructor.

## Scope

Scope is a plain dict. The SDK serialises it to the wire format the server
expects.

```python
memory.remember("...", scope={"org": "acme"})
memory.documents.upload("returns.pdf", scope={"org": "acme", "user": "tobie"})
```

## Authentication

Every request carries `Authorization: Bearer <api_key>` and no other
auth-related header. There is no env-var fallback, no URL default, and no
alternative scheme — pass the key explicitly to the constructor.
