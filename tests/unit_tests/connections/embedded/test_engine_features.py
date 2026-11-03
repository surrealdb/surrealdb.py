"""The embedded engine ships every SurrealQL function family the server does.

From SurrealDB 4.0, `surrealdb-core` gates most of its function families behind
cargo features that are on by default. The extension builds the engine with
`default-features = false` to leave out GraphQL and the wire protocols it has
no use for, so each family it does want has to be named in
embedded/Cargo.toml. A family left off still parses, and fails only when it is
called, with "This build was compiled without the `<feature>` feature". These
cases call one function from each, so dropping a feature fails here rather than
in a user's query.
"""

from collections.abc import Generator

import pytest

from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection

FEATURE_QUERIES = {
    "crypto-password": "RETURN crypto::argon2::compare(crypto::argon2::generate('x'), 'x')",
    "crypto-digest": "RETURN crypto::sha256('x')",
    "geo": "RETURN geo::distance((0, 0), (1, 1))",
    "collate": "RETURN string::slug('Ünïcödé text')",
    "url": "RETURN parse::url::host('https://surrealdb.com/docs')",
    "encoding": "RETURN encoding::base64::encode(<bytes>'x')",
    "html-sanitize": "RETURN string::html::sanitize('<script>x</script><b>y</b>')",
    "regex-unicode": r"RETURN 'Ünï' = /^\p{L}+$/",
    "fulltext": (
        "DEFINE ANALYZER simple TOKENIZERS blank FILTERS lowercase;"
        "DEFINE INDEX ft ON doc FIELDS body FULLTEXT ANALYZER simple BM25;"
        "CREATE doc:1 SET body = 'hello world';"
        "SELECT id, search::score(1) AS score FROM doc WHERE body @1@ 'hello';"
    ),
    "vector-index": (
        "DEFINE INDEX hnsw ON vec FIELDS v HNSW DIMENSION 2;"
        "CREATE vec:1 SET v = [1, 2];"
        "SELECT id FROM vec WHERE v <|1,10|> [1, 2];"
    ),
    "api": (
        "DEFINE API '/hello' FOR get THEN { RETURN { status: 200, body: 'hi' } };"
        "RETURN api::invoke('/hello');"
    ),
    "files": (
        "DEFINE BUCKET b BACKEND 'memory';"
        "f'b:/a.txt'.put('x');"
        "RETURN f'b:/a.txt'.get();"
    ),
}


@pytest.fixture
def embedded() -> Generator[BlockingEmbeddedSurrealConnection, None, None]:
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("test_ns", "test_db")
    yield connection
    connection.close()


@pytest.mark.parametrize("query", FEATURE_QUERIES.values(), ids=FEATURE_QUERIES.keys())
def test_function_family_is_compiled_in(
    embedded: BlockingEmbeddedSurrealConnection, query: str
) -> None:
    response = embedded.query_raw(query)

    assert "error" not in response, response["error"]
    failed = [r["result"] for r in response["result"] if r["status"] != "OK"]
    assert not failed, failed


def test_text_diffs_patch_strings_rather_than_replacing_them(
    embedded: BlockingEmbeddedSurrealConnection,
) -> None:
    """Without `text-diff` a changed string degrades to a whole `replace`
    instead of failing, so it needs its own assertion."""
    response = embedded.query_raw(
        "CREATE t:1 SET s = 'hello world'; UPDATE t:1 SET s = 'hello there' RETURN DIFF;"
    )

    [diff] = response["result"][-1]["result"]
    assert [op["op"] for op in diff] == ["change"], diff
