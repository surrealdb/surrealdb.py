from uuid import UUID

import pytest


def test_query(blocking_ws_connection_with_user):
    outcome = blocking_ws_connection_with_user.live("user")
    assert isinstance(outcome, UUID)
