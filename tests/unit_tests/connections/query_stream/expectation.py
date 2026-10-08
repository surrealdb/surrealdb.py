"""What CI says the server under test should do about streaming.

Every streaming test used to skip itself when the server refused to stream, and
that is right on a server older than v3.3.0 - but it is also what a regression
looks like, and a skipped test is green. A v3.3.0 job in which the server's
streaming quietly stopped being recognised would have reported every streaming
test as skipped and passed.

CI therefore says what it expects: ``SURREALDB_EXPECT_STREAMING=1`` on a server
that must stream, ``0`` on one that must not. With ``1``, a refusal fails the
test instead of skipping it; with ``0``, :mod:`test_version_gate` asserts the
fallback. Unset - a developer's own server - nothing is asserted and the old
skipping behaviour stands.
"""

import os
from typing import NoReturn

import pytest

ENV = "SURREALDB_EXPECT_STREAMING"


def streaming_expected() -> bool | None:
    """True or False when CI has said which, None when nobody has."""
    value = os.environ.get(ENV)
    if value is None or value == "":
        return None
    return value == "1"


def skip_unless_streaming_is_expected(reason: object) -> NoReturn:
    """Skip a streaming test the server refuses, unless it was meant to stream."""
    if streaming_expected():
        pytest.fail(
            f"{ENV}=1 says this server must stream, but it refused: {reason}",
            pytrace=False,
        )
    pytest.skip(f"this server will not stream: {reason}")
