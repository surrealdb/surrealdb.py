"""SurrealDB 4.0's regex, and how it crosses the wire."""

import re

import pytest

from surrealdb import Regex
from surrealdb.data import cbor
from surrealdb.errors import UnexpectedResponseError


def test_a_regex_is_its_pattern() -> None:
    value = Regex(r"^\d+$")
    assert value.pattern == r"^\d+$"
    assert str(value) == r"^\d+$"
    assert repr(value) == r"Regex('^\\d+$')"
    assert value == Regex(r"^\d+$")
    assert len({value, Regex(r"^\d+$")}) == 1
    assert value != r"^\d+$"


def test_a_pattern_that_is_not_text_is_refused() -> None:
    with pytest.raises(TypeError):
        Regex(re.compile("a"))  # type: ignore[arg-type]


def test_a_regex_is_tag_193_over_cbor2() -> None:
    raw = cbor.encode(Regex("a.*"), v2=True)
    assert raw.hex() == "d8c163612e2a"
    assert cbor.decode(raw, v2=True) == Regex("a.*")


def test_a_regex_cannot_be_sent_over_plain_cbor() -> None:
    with pytest.raises(ValueError, match="plain cbor"):
        cbor.encode(Regex("a.*"))


@pytest.mark.parametrize("v2", [False, True])
def test_a_compiled_pattern_is_refused_with_a_way_to_send_it(v2: bool) -> None:
    with pytest.raises(TypeError, match=r"Regex\("):
        cbor.encode(re.compile("a.*"), v2=v2)


def test_a_regex_is_refused_outside_cbor2() -> None:
    with pytest.raises(UnexpectedResponseError, match=r"outside cbor\.2"):
        cbor.decode(bytes.fromhex("d8c163612e2a"))
