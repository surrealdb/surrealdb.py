from typing import Any

import pytest

from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


def test_request_message_init() -> None:
    method = RequestMethod.USE
    request_message = RequestMessage(method, one="two", three="four")
    assert request_message.method == method
    assert request_message.kwargs == {"one": "two", "three": "four"}


def test_request_method_session_txn_values() -> None:
    assert RequestMethod.ATTACH.value == "attach"
    assert RequestMethod.DETACH.value == "detach"
    assert RequestMethod.BEGIN.value == "begin"
    assert RequestMethod.COMMIT.value == "commit"
    assert RequestMethod.CANCEL.value == "cancel"
