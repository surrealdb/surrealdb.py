"""The embedded engine has no /export or /import endpoint, and says so."""

import pytest

from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
from surrealdb.errors import UnsupportedFeatureError


def test_blocking_export_and_import_are_refused() -> None:
    connection = BlockingEmbeddedSurrealConnection("memory")
    with pytest.raises(UnsupportedFeatureError, match="/export"):
        connection.export()
    with pytest.raises(UnsupportedFeatureError, match="/export"):
        connection.export_to("unused.surql")
    with pytest.raises(UnsupportedFeatureError, match="/import"):
        connection.import_("OPTION IMPORT;")


async def test_async_export_and_import_are_refused() -> None:
    connection = AsyncEmbeddedSurrealConnection("memory")
    with pytest.raises(UnsupportedFeatureError, match="/export"):
        await connection.export()
    with pytest.raises(UnsupportedFeatureError, match="/export"):
        await connection.export_to("unused.surql")
    with pytest.raises(UnsupportedFeatureError, match="/import"):
        await connection.import_("OPTION IMPORT;")
