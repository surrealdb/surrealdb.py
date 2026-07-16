# Spectron

Python client for [Spectron](https://github.com/surrealdb/spectron), bundled
with `surrealdb`.

```python
from surrealdb.spectron import Spectron

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
from surrealdb.spectron import Spectron, AsyncSpectron

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

The client covers the full Spectron end-user API. Headline verbs are methods on
the client; grouped resources live under namespaces (`memory.documents.…`,
`memory.sessions.…`, etc.). Both `Spectron` and `AsyncSpectron` expose the same
names — `await` the async one.

### Memory verbs

| Method | Endpoint |
| --- | --- |
| `remember(text, ...)` | `POST /api/v1/{context}/facts` |
| `remember_many(items, ...)` | `POST /api/v1/{context}/facts/batch` |
| `recall(query, ...)` | `POST /api/v1/{context}/query` |
| `forget(query, ...)` | `POST /api/v1/{context}/forget` |
| `chat(message, stream=…)` | `POST /api/v1/{context}/chat` (SSE if `stream=True`) |
| `consolidate(...)` | `POST /api/v1/{context}/consolidate` |
| `reflect(query, ...)` | `POST /api/v1/{context}/reflect` |
| `elaborate(...)` | `POST /api/v1/{context}/elaborate` |
| `query_context(query, ...)` | `POST /api/v1/{context}/context` |
| `inspect(ref, ...)` | `GET /api/v1/{context}/inspect` |
| `state()` | `GET /api/v1/{context}/state` |
| `audit(...)` | `GET /api/v1/{context}/audit` |
| `whoami()` | `GET /api/v1/{context}/me` |
| `profile()` | `GET /api/v1/{context}/profile` |
| `health()` | `GET /api/v1/health` (not context-scoped) |

### Namespaces

| Namespace | Methods |
| --- | --- |
| `documents` | `upload`, `get`, `delete`, `list`, `query`, `fetch_raw`, `reprocess`, `recompute_links`, `chunks` |
| `documents.keywords` | `list`, `get`, `search`, `for_document` |
| `sessions` | `create`, `delete`, `context`, `turns` |
| `entities` | `list`, `get`, `delete`, `history` |
| `scopes` | `register`, `list`, `delete`, `forget` |
| `principals` | `list`, `get`, `grant`, `revoke`, `effective` |
| `keys` | `create`, `list`, `delete`, `rotate` |
| `traces` | `list`, `get`, `stats` |
| `lifecycle` | `decay`, `expire`, `fsck` |

### Remember

```python
memory.remember("I work at Acme as CTO")
memory.remember("Acme acquired Beta", session_id="sess:abc", scopes="org/acme")
memory.remember("Q3 board notes", labels=["topic=board"], memory_category="context")

memory.remember_many(
    [
        {"role": "user", "content": "I just got promoted to CTO"},
        {"role": "assistant", "content": "Congratulations!"},
    ],
    extract="whole_conversation",
)
```

`infer` selects the extraction path (`full`, `triples`, `preview`, `none`).
`remember_many` also takes `extract` (`per_message` or `whole_conversation`).
`labels` are `key=value` strings recorded on the rows.

`remember` and `remember_many` set an `Idempotency-Key` header derived from
`sha256(method | path | body | 30s-bucket)`, so a retry inside the bucket
collapses onto the previous attempt server-side.

### Recall

```python
result = memory.recall("what role do I have at Acme", k=10, mode="hybrid")
for hit in result.hits:
    print(hit.score, hit.source, hit.text)
```

Optional filters: `labels` (a `key=value` path list), `lens` (a read scope
selector taking the same DNF shape as `scopes`, see [Scope](#scope)),
`scope_view` (`strict` | `merged` | `crossTeam`), `include` (`facts`,
`passages`), the temporal bounds `as_of` / `at_instant` / `valid_from` /
`valid_until`, and a `location` geo filter
(`{"near": {"lat": ..., "lng": ..., "radiusKm": ...}}` or `{"within": "<WKT>"}`).

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
result = memory.documents.upload(
    "returns.pdf",
    content_type="application/pdf",
    title="Returns policy",
    source="kb",
    scopes="org/acme",
)
print(result.id, result.status)
```

`path` accepts a filesystem path, bytes, or a file-like object. `title`,
`source`, and `scopes` are optional and ride along as the document's metadata.
`scopes` takes the same DNF shape as the write verbs (see [Scope](#scope)); each
path must lie within the key's write region, and omitting it falls back to the
whole write region.

The rest of the document surface manages the corpus:

```python
page = memory.documents.list(status="Ready", page=1, page_size=20)
doc = memory.documents.get("document:abc")
hits = memory.documents.query("refund window", k=5, mode="hybrid")
raw = memory.documents.fetch_raw("document:abc")          # -> bytes
memory.documents.reprocess("document:abc")
memory.documents.recompute_links()
chunks = memory.documents.chunks("document:abc")

# Keyword index (corpus-level)
memory.documents.keywords.list(q="refund")
memory.documents.keywords.get("refund")
memory.documents.keywords.search("returns policy", k=10)
memory.documents.keywords.for_document("document:abc")
```

### Consolidate, reflect, elaborate

```python
# Pool recent facts into durable observations (preview with dry_run=True).
outcome = memory.consolidate(dry_run=True)
print(outcome.created, outcome.superseded, outcome.outcomes)

# Summarise what the store knows, optionally persisting the reflection.
memory.reflect("what are my preferences", persist=True)

# Expand an entity's relations from existing memory.
memory.elaborate(entity_ref="entity:person/stu")
```

### Introspection

```python
memory.state()                      # working-memory snapshot
memory.whoami()                     # caller identity + effective grants
memory.profile()                    # static/dynamic profile entries
memory.inspect("entity:person/stu") # raw, kind-discriminated payload
memory.query_context("who is stu")  # composed context string
```

### Sessions, entities, scopes

```python
session = memory.sessions.create(scopes="org/acme")
memory.sessions.context(session.id, "recap our last call")
memory.sessions.turns(session.id, limit=20)

memory.entities.list(entity_type="person")
memory.entities.get("person", "Stu")
memory.entities.history("person", "Stu", "role")

memory.scopes.register("org/acme/", display_name="Acme")
memory.scopes.list()
memory.scopes.forget("user/stu/")
```

### Access control: principals & self-service keys

```python
memory.principals.list()
memory.principals.grant("agent-7", "org/acme/*", ["memory:read", "memory:write"])
memory.principals.effective("agent-7", "org/acme/")

minted = memory.keys.create(name="ci", ttl_seconds=3600)
print(minted.key)                   # full bearer key, shown once
memory.keys.rotate("ci")
memory.keys.list()
```

### Observability & maintenance

```python
memory.traces.list(limit=50)
memory.traces.get("trace:xyz")
memory.traces.stats()
memory.audit(kind="decision", limit=100)   # access/cost log

memory.lifecycle.decay()                    # age out importance
memory.lifecycle.expire()                   # drop expired rows
memory.lifecycle.fsck(check="duplicates")   # integrity report
```

## Errors

```python
from surrealdb.spectron import SpectronAPIError, SpectronNotFoundError

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

`scopes` is a DNF (disjunctive-normal-form) selector: an OR of conjunctive
clauses, serialised on the wire as `array<array<string>>`. The outer list ORs
across clauses; each inner list ANDs the scope paths within a clause. The same
shape is used by the write verbs (`scopes`) and the read lens (`lens`). Omit it
to use the key's default write region.

The facade accepts these input forms:

- A single path string is one singleton clause: `"team/eng"` -> `[["team/eng"]]`.
- A flat list of paths is an OR of singletons:
  `["team/eng", "org/acme"]` -> `[["team/eng"], ["org/acme"]]` (eng OR acme).
- A nested list is an AND clause:
  `[["team/eng", "org/acme"]]` -> `[["team/eng", "org/acme"]]` (eng AND acme).
- The string and nested forms mix freely:
  `["team/eng", ["org/acme", "region/eu"]]` ->
  `[["team/eng"], ["org/acme", "region/eu"]]`.

```python
memory.remember("...", scopes="team/eng")
memory.remember("...", scopes=["team/eng", "org/acme"])     # eng OR acme
memory.remember("...", scopes=[["team/eng", "org/acme"]])   # eng AND acme
```

## Authentication

Every request carries `Authorization: Bearer <api_key>`. 

### Delegation (on-behalf-of)

Every verb takes an optional `on_behalf_of` argument. When set, the request
carries `X-Spectron-On-Behalf-Of: <principal>` and the server runs it as that
principal, with effective grants narrowed to `caller ∩ target` (the caller can
only delegate to a principal it is allowed to act for). The value may be a bare
principal id or the `principal:<id>` form; it is sent verbatim.

```python
memory.recall("open tickets", on_behalf_of="principal:agent-7")
memory.remember("ticket triaged", on_behalf_of="principal:agent-7")
```

Delegation is per call, so a single client can act for different principals on
different requests.
