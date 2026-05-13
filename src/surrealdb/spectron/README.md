# Spectron SDK

Python client for the Spectron memory + knowledge service, shipped as an in-tree subpackage of `surrealdb`.

```python
from surrealdb import Spectron

memory = Spectron(context="acme-prod", api_key=os.environ["SPECTRON_API_KEY"])
hits = memory.knowledge.query("returns policy", k=5)
```

No extra install step: the SDK is bundled with `pip install surrealdb`.

## Contents

- [Clients](#clients)
- [Authentication](#authentication)
- [Knowledge: documents, query, keywords, nodes, traversal](#knowledge)
- [Memory: sessions, retrieval, state, profile, entities, traces](#memory)
- [Management: contexts, keys, config](#management)
- [Errors](#errors)
- [Retries & timeouts](#retries--timeouts)
- [Scope](#scope)
- [Wire-shape types](#wire-shape-types)

## Clients

Four top-level facades, all importable from `surrealdb`:

| Class | Surface | Transport |
|---|---|---|
| `Spectron` | end-user, context-scoped | blocking (`requests`) |
| `AsyncSpectron` | end-user, context-scoped | async (`aiohttp`) |
| `SpectronManagement` | control plane | blocking |
| `AsyncSpectronManagement` | control plane | async |

End-user clients require a context id and target `/api/v1/{context_id}/...`. Management clients target `/api/v1/contexts/...` and need a management-tier key.

```python
from surrealdb import Spectron, AsyncSpectron, SpectronManagement, AsyncSpectronManagement

with Spectron(context="acme-prod", api_key="...") as memory:
    state = memory.state()

async with AsyncSpectron(context="acme-prod", api_key="...") as memory:
    state = await memory.state()

with SpectronManagement(api_key="...") as admin:
    contexts = admin.contexts.list()
```

Constructor arguments (identical across all four):

| Arg | Default | Notes |
|---|---|---|
| `context` (positional, end-user only) | required | Context id, e.g. `"acme-prod"`. |
| `base_url` | `https://api.spectron.dev` | Override for self-hosted. |
| `api_key` | required | Bearer token. |
| `timeout` | `30.0` seconds | Per-request. |
| `max_retries` | `3` | GET-only, see [Retries](#retries--timeouts). |
| `transport` | `None` | Inject a custom transport for testing. |

## Authentication

Pass `api_key=` explicitly. The transport adds `Authorization: Bearer <key>` to every request and does not pre-check principal type; the server returns `403` if the key's principal or scope floor rejects the call.

## Knowledge

### Documents

```python
doc = memory.knowledge.upload(
    file="returns.pdf",                  # path | bytes | file-like
    title="Returns Policy",
    profile="multimodal_balanced",       # text_only | text_plus_ocr | multimodal_balanced | multimodal_full
    scope={"org": "anneal"},
)
# doc.id, doc.status, doc.content_hash, doc.deduplicated

doc = memory.knowledge.get(doc.id)
memory.knowledge.replace(doc.id, file=open("returns_v2.pdf", "rb"))
raw_bytes = memory.knowledge.raw(doc.id)
chunks = memory.knowledge.chunks(doc.id, page=0, page_size=50)
docs = memory.knowledge.list(status="ready", mime_type="application/pdf")
related = memory.knowledge.related(doc.id)
memory.knowledge.delete(doc.id)
```

### Query

```python
from surrealdb import SpectronQueryMode

hits = memory.knowledge.query(
    "what is the return window for unopened items?",
    mode=SpectronQueryMode.HYBRID_GRAPH,  # vector | bm25 | hybrid | hybrid_graph
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
# hits.query_ms, hits.results[].score, .chunk, .document, .graph_evidence
```

### Keyword graph

```python
keywords = memory.knowledge.keywords.list(min_document_count=2, sort="-document_count", q="return")
detail   = memory.knowledge.keywords.get("RETURN POLICY")
similar  = memory.knowledge.keywords.search("refund policies", k=10, threshold=0.6)
related  = memory.knowledge.keywords.related("RETURN POLICY")
for_doc  = memory.knowledge.keywords.for_document(doc.id)
```

### Typed nodes

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

nodes   = memory.knowledge.nodes.list(kind="product")
hits    = memory.knowledge.nodes.search("audio products", k=10)
node    = memory.knowledge.nodes.get("product", "airpods_pro_2")
related = memory.knowledge.nodes.related("product", "airpods_pro_2")
memory.knowledge.nodes.delete("product", "airpods_pro_2")
```

### Graph traversal

```python
walk = memory.knowledge.traverse(
    start=[{"type": "document", "id": doc.id}],
    edges=["knowledge_has_keyword", "knowledge_relates_to"],
    max_depth=2,
)

recursive = memory.knowledge.traverse_recursive(
    start={"type": "knowledge", "kind": "product", "slug": "airpods_pro_2"},
    edge="knowledge_relates_to",
    max_depth=3,
)

siblings = memory.knowledge.traverse_siblings(
    start={"type": "knowledge", "kind": "product", "slug": "airpods_pro_2"},
    edge="knowledge_relates_to",
)
```

## Memory

### Sessions

Two integration shapes: Spectron drives the loop, or the caller does.

**Spectron drives:**

```python
session = memory.sessions.create(scope={"user": "tobie"})
reply = session.chat("What do you know about me?")
# reply.reply (assistant text), reply.memory_updates (ExtractionResult)
session.close()
```

**Caller drives:**

```python
session = memory.sessions.create(scope={"user": "tobie"})

diff = session.turn("user", "I just got promoted to CTO")
# diff.entities, diff.attributes, diff.relations, diff.instructions, ...

ctx = session.context(query="What is Tobie's role?")
# Inject ctx.context into your own LLM prompt
reply = my_llm.chat(system=ctx.context, user=user_message)

session.turn("assistant", reply)

turns = session.turns()
session.close()
```

### One-shot retrieval

```python
hits = memory.query("What role does Christian have?", k=10)
# hits.tier, hits.hits[], hits.query_ms, hits.trace

ctx = memory.context("brief on tobie", k=10)
# ctx.context (string ready for system-prompt injection)
```

### State, profile, entities

```python
state = memory.state()         # StructuredState: identity / knowledge / context / instructions / unknowns
profile = memory.profile()     # ProfileResponse: static / dynamic / preferences / instructions

entities = memory.entities.list(type="Person")
entity   = memory.entities.get("Person", "christian_battaglia")
history  = memory.entities.history("Person", "christian_battaglia", key="role")
memory.entities.delete("Person", "christian_battaglia")  # soft-delete
```

### Reflection, forget, lifecycle

```python
out = memory.reflect("patterns in customer complaints this month?", persist=True)
# out.reflection, out.evidence, out.persisted_attributes

result = memory.forget("anything about my old job")
# result.deleted = number of memories soft-deleted by similarity match

memory.lifecycle.expire()   # context-category expiry sweep
memory.lifecycle.decay()    # importance decay sweep
```

### Traces

```python
traces = memory.traces.list(limit=50)
trace  = memory.traces.get("decision_trace:abc123")
stats  = memory.traces.stats()
# stats.total_queries, stats.cache_hits, stats.avg_latency_ms, stats.tier_counts
```

## Management

Control-plane operations need a management-tier API key.

```python
from surrealdb import SpectronManagement, SpectronPrincipalType

admin = SpectronManagement(api_key=os.environ["SPECTRON_MGMT_KEY"])

admin.contexts.create(
    "acme-prod",
    namespace="acme",
    database="prod",
    config={"models": {"extraction": "gpt-4o-mini", "response": "gpt-4o"}},
)
admin.contexts.update("acme-prod", config={"models": {"reflection": "gpt-4o"}})
ctx = admin.contexts.get("acme-prod")
admin.contexts.list()
admin.contexts.delete("acme-prod")

# Per-context API keys
created = admin.contexts("acme-prod").keys.create(
    name="planner",
    principal=SpectronPrincipalType.AGENT,
    scope_floor={"org": "anneal", "agent": "planner"},
    expires_at="2027-01-01T00:00:00Z",
)
# created.key: store it now, it is not retrievable later.

admin.contexts("acme-prod").keys.list()
admin.contexts("acme-prod").keys.delete("planner")
```

End-user clients also expose a `config` shortcut that wraps `PATCH /contexts/{id}` (management-key only):

```python
memory.config.models(extraction="gpt-4o-mini", response="gpt-4o")
memory.config.providers(openai=os.environ["OPENAI_API_KEY"])
memory.config.ontology(
    entity_types=["Customer", "Product", "Ticket"],
    attribute_keys={"Customer": ["name", "plan", "region"]},
    relation_labels=["purchased", "raised", "resolved_by"],
)
```

## Errors

The server returns RFC 7807 problem details; the SDK maps them to a typed hierarchy. Top-level aliases are prefixed with `Spectron` to avoid clashing with `surrealdb.errors`.

| Class (subpackage) | Top-level alias | HTTP | When |
|---|---|---|---|
| `SpectronError` | `SpectronError` | any | Base for every transport-level error. |
| `AuthError` | `SpectronAuthError` | 401 | Missing or invalid bearer token. |
| `ScopeError` | `SpectronScopeError` | 403 | Principal type or scope floor rejected the call. |
| `NotFoundError` | `SpectronNotFoundError` | 404 | Resource does not exist. |
| `ValidationError` | `SpectronValidationError` | 400 / 422 | Malformed body, unknown enum, invalid context id. |
| `RateLimitError` | `SpectronRateLimitError` | 429 | Per-context rate or token budget exceeded. Carries `retry_after`. |
| `ServerError` | `SpectronServerError` | 5xx | Retried for idempotent reads. |

Every exception carries `status`, `title`, `detail`, `type_uri`, `instance`, and `extensions` parsed from the problem-details body.

```python
from surrealdb import SpectronNotFoundError, SpectronRateLimitError

try:
    doc = memory.knowledge.get("doc:missing")
except SpectronNotFoundError as e:
    print(e.status, e.detail)
except SpectronRateLimitError as e:
    print("retry after", e.retry_after, "seconds")
```

## Retries & timeouts

- Idempotent reads (`GET`) auto-retry on connection failures and 5xx with exponential backoff `[250ms, 500ms, 1s]`, max 3 attempts. Tune via `max_retries=`.
- Writes (`POST` / `PUT` / `PATCH` / `DELETE`) never auto-retry; the caller decides.
- Default per-request timeout is 30 seconds. Override via `timeout=` on the constructor or on individual `transport.request(...)` calls.

## Scope

Scope is a plain dict in user code; the SDK serialises it to the `set<scope_attribute>` wire shape. Subset-matching and floor enforcement are server-side; the SDK does not pre-check.

```python
session_a = memory.sessions.create(scope={"org": "anneal"})

session_b = memory.sessions.create(
    scope={"org": "anneal", "user": "tobie", "project": "spectron"}
)
```

Manual helpers if you need them:

```python
from surrealdb.spectron import serialise_scope, deserialise_scope

wire = serialise_scope({"org": "anneal"})           # [{"key": "org", "value": "anneal"}]
back = deserialise_scope(wire)                      # {"org": "anneal"}
```

## Wire-shape types

Every dataclass is re-exported under `surrealdb.spectron.*` (e.g. `DocumentJson`, `QueryResponseJson`, `ContextResponse`, `SessionInfo`, `ExtractionResult`, `TraceStats`, ...) for callers that want typed access without going through the namespaces.
