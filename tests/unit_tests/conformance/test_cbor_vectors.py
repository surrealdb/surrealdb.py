"""The shared CBOR value vectors from surrealdb-protocol, run against this codec.

``vectors/VERSION`` names the surrealdb-protocol release they come from;
``scripts/protocol-vectors.sh`` fetches them, and the tests skip until it has. ``cbor.yaml`` is the plain
``cbor`` wire, and every vector in it whose ``formats`` does not leave ``cbor.2``
out holds for ``cbor.2`` too. ``cbor2.yaml`` is ``cbor.2`` only.

For each vector (spec/README.md, "Using the vectors from an SDK"):

- canonical: the bytes decode to the value, and the value encodes to bytes
  that decode back to it.
- decode: the bytes decode to the value.
- reject: decoding the bytes raises.
"""

from pathlib import Path
from typing import Any

import pytest

from conformance.typed_json import same, to_json, to_native
from surrealdb.data.cbor import decode, encode

_VECTORS = Path(__file__).parent / "vectors"

if not (_VECTORS / "cbor.yaml").exists():
    pytest.skip(
        "no protocol vectors; fetch them with scripts/protocol-vectors.sh",
        allow_module_level=True,
    )

yaml = pytest.importorskip("yaml")


def _load(name: str) -> list[dict[str, Any]]:
    with open(_VECTORS / name, encoding="utf-8") as fp:
        return list(yaml.safe_load(fp)["vectors"])


def _cases() -> list[Any]:
    cases = []
    for vector in _load("cbor.yaml"):
        for v2, wire in ((False, "cbor"), (True, "cbor.2")):
            if wire in vector.get("formats", ["cbor", "cbor.2"]):
                cases.append(pytest.param(vector, v2, id=f"{wire}:{vector['name']}"))
    for vector in _load("cbor2.yaml"):
        cases.append(pytest.param(vector, True, id=f"cbor.2:{vector['name']}"))
    return cases


def test_the_vectors_are_pinned_to_a_release() -> None:
    assert (_VECTORS / "VERSION").read_text().strip().startswith("v")


@pytest.mark.parametrize(("vector", "v2"), _cases())
def test_vector(vector: dict[str, Any], v2: bool) -> None:
    data = bytes.fromhex(vector["cbor"])
    if vector["kind"] == "reject":
        with pytest.raises(Exception):  # noqa: B017
            decode(data, v2=v2)
        return

    expected = to_native(vector["value"])
    decoded = decode(data, v2=v2)
    assert same(expected, decoded), f"{to_json(decoded)} != {vector['value']}"

    if vector["kind"] == "canonical":
        round_trip = decode(encode(expected, v2=v2), v2=v2)
        assert same(expected, round_trip), f"{to_json(round_trip)} != {vector['value']}"
