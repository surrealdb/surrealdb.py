# Spectron

Python client for Spectron, bundled with `surrealdb`.

```python
from surrealdb import Spectron

memory = Spectron(
    context="acme-prod",
    base_url="https://api.spectron.example",
    api_key="sk-spec-...",
)
hits = memory.knowledge.query("returns policy", k=5)
```

## Install

```
pip install surrealdb
```

## Clients

```python
from surrealdb import Spectron, AsyncSpectron

with Spectron(context="acme-prod", base_url="https://api.spectron.example", api_key="sk-...") as memory:
    state = memory.state()

async with AsyncSpectron(context="acme-prod", base_url="https://api.spectron.example", api_key="sk-...") as memory:
    state = await memory.state()
```

`Spectron` uses `requests`. `AsyncSpectron` uses `aiohttp`. Same method names on both; add `await` for the async one.

Both clients are pinned to one context and hit `/api/v1/{context}/...`.

### Constructor

| Arg | Default | |
|---|---|---|
| `context` | required | Context id, e.g. `"acme-prod"`. |
| `base_url` | required | Full URL of the Spectron host, e.g. `"https://api.spectron.example"`. No default. |
| `api_key` | required | Bearer token, as a string. |
| `timeout` | `30.0` | Seconds per request. |
| `max_retries` | `3` | GET-only retries. |
| `transport` | `None` | Inject your own for testing. |

Pass `api_key` as a string from wherever you keep secrets. The SDK never reads environment variables.

## Knowledge

### Documents

```python
doc = memory.knowledge.upload(
    file="returns.pdf",
    title="Returns Policy",
    profile="multimodal_balanced",
    scope={"org": "anneal"},
)

memory.knowledge.get(doc.id)
memory.knowledge.replace(doc.id, file=open("returns_v2.pdf", "rb"))
memory.knowledge.raw(doc.id)
memory.knowledge.chunks(doc.id, page=0, page_size=50)
memory.knowledge.list(status="ready", mime_type="application/pdf")
memory.knowledge.related(doc.id)
memory.knowledge.delete(doc.id)
```

`file` accepts a path, bytes, or a file-like object.
`profile` is one of `text_only`, `text_plus_ocr`, `multimodal_balanced`, `multimodal_full`.

### Query

```python
from surrealdb import SpectronQueryMode

hits = memory.knowledge.query(
    "what is the return window for unopened items?",
    mode=SpectronQueryMode.HYBRID_GRAPH,
    k=10,
    threshold=0.5,
    vector_weight=0.5,
    rrf_k=60,
    graph_alpha=0.3,
    graph_edges=["knowledge_has_keyword", "knowledge_relates_to"],
    graph_depth=2,
    expand_graph=True,
    filter={"mime_type": ["application/pdf"], "scope": {"org": "anneal"}},
)
```

`mode` is `vector`, `bm25`, `hybrid`, or `hybrid_graph`.

### Keywords

```python
memory.knowledge.keywords.list(min_document_count=2, sort="-document_count", q="return")
memory.knowledge.keywords.get("RETURN POLICY")
memory.knowledge.keywords.search("refund policies", k=10, threshold=0.6)
memory.knowledge.keywords.related("RETURN POLICY")
memory.knowledge.keywords.for_document(doc.id)
```

### Nodes

```python
from surrealdb.spectron import KnowledgeNodeUpsertRow, KnowledgeLinkUpsert, KnowledgeLinkTarget

memory.knowledge.nodes.upsert(
    nodes=[
        KnowledgeNodeUpsertRow(kind="product", slug="airpods_pro_2", title="AirPods Pro 2",
                               content={"price": 249, "category": "Audio"}),
        KnowledgeNodeUpsertRow(kind="policy", slug="returns", title="Returns",
                               content={"duration": "30 days"}),
    ],
    relations=[
        KnowledgeLinkUpsert(label="covered_by",
                            to=KnowledgeLinkTarget(kind="policy", slug="returns")),
    ],
    scope={"org": "apple"},
)

memory.knowledge.nodes.list(kind="product")
memory.knowledge.nodes.search("audio products", k=10)
memory.knowledge.nodes.get("product", "airpods_pro_2")
memory.knowledge.nodes.related("product", "airpods_pro_2")
memory.knowledge.nodes.delete("product", "airpods_pro_2")
```

### Traversal

```python
memory.knowledge.traverse(
    start=[{"type": "document", "id": doc.id}],
    edges=["knowledge_has_keyword", "knowledge_relates_to"],
    max_depth=2,
)

memory.knowledge.traverse_recursive(
    start={"type": "knowledge", "kind": "product", "slug": "airpods_pro_2"},
    edge="knowledge_relates_to",
    max_depth=3,
)

memory.knowledge.traverse_siblings(
    start={"type": "knowledge", "kind": "product", "slug": "airpods_pro_2"},
    edge="knowledge_relates_to",
)
```

## Sessions

Let Spectron run the chat loop:

```python
session = memory.sessions.create(scope={"user": "tobie"})
reply = session.chat("What do you know about me?")
session.close()
```

Or drive it yourself:

```python
session = memory.sessions.create(scope={"user": "tobie"})

session.turn("user", "I just got promoted to CTO")

ctx = session.context(query="What is Tobie's role?")
reply = my_llm.chat(system=ctx.context, user=user_message)
session.turn("assistant", reply)

session.turns()
session.close()
```

## One-shot retrieval

```python
memory.query("What role does Christian have?", k=10)
memory.context("brief on tobie", k=10)
```

## State, profile, entities

```python
memory.state()
memory.profile()

memory.entities.list(type="Person")
memory.entities.get("Person", "christian_battaglia")
memory.entities.history("Person", "christian_battaglia", key="role")
memory.entities.delete("Person", "christian_battaglia")
```

`entities.delete` is a soft delete.

## Reflect, forget, lifecycle

```python
memory.reflect("patterns in customer complaints this month?", persist=True)

memory.forget("anything about my old job")

memory.lifecycle.expire()
memory.lifecycle.decay()
```

## Traces

```python
memory.traces.list(limit=50)
memory.traces.get("decision_trace:abc123")
memory.traces.stats()
```

## Errors

```python
from surrealdb import SpectronNotFoundError, SpectronRateLimitError

try:
    memory.knowledge.get("doc:missing")
except SpectronNotFoundError as e:
    print(e.status, e.detail)
except SpectronRateLimitError as e:
    print("retry after", e.retry_after, "seconds")
```

| Exception | HTTP |
|---|---|
| `SpectronError` | base |
| `SpectronAuthError` | 401 |
| `SpectronScopeError` | 403 |
| `SpectronNotFoundError` | 404 |
| `SpectronValidationError` | 400, 422 |
| `SpectronRateLimitError` | 429 (with `retry_after`) |
| `SpectronServerError` | 5xx |

Each carries `status`, `title`, `detail`, `type_uri`, `instance`, `extensions`.

## Retries and timeouts

- `GET` retries on connection errors and 5xx: 250ms, 500ms, 1s. Up to `max_retries` (default 3).
- Writes never retry. You handle it.
- Default timeout is 30s. Override with `timeout=` on the constructor.

## Scope

Scope is a plain dict. The SDK serialises it to the wire format. Server enforces matching and floors.

```python
memory.sessions.create(scope={"org": "anneal"})
memory.sessions.create(scope={"org": "anneal", "user": "tobie", "project": "spectron"})
```

If you need the raw conversion:

```python
from surrealdb.spectron import serialise_scope, deserialise_scope

serialise_scope({"org": "anneal"})    # [{"key": "org", "value": "anneal"}]
deserialise_scope([...])              # {"org": "anneal"}
```

## Types

Every wire shape is a dataclass under `surrealdb.spectron`: `DocumentJson`, `QueryResponseJson`, `SessionInfo`, `ExtractionResult`, `TraceStats`, and so on. Use them directly if you want the types without going through the client methods.
