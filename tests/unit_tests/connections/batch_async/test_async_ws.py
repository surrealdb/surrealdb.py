import asyncio
import os
import sys

import pytest


async def test_batch(async_ws_connection):
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    # async batching doesn't work for surrealDB v2.1.0" or lower
    surrealdb_version = os.environ.get("SURREALDB_VERSION")
    if surrealdb_version == "v2.1.0":
        pass
    elif python_version == "3.9" or python_version == "3.10":
        print(
            "async batching is being bypassed due to python versions 3.9 and 3.10 not supporting async task group"
        )
    else:
        if surrealdb_version and surrealdb_version.startswith("v2"):
            sleep_fn = "duration::from::millis"
        else:
            sleep_fn = "duration::from_millis"

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(
                    async_ws_connection.query(
                        f"RETURN sleep({sleep_fn}($d)) or $p**2",
                        dict(d=10 if num % 2 else 0, p=num),
                    )
                )
                for num in range(5)
            ]

        outcome = [t.result() for t in tasks]
        assert [0 == 1, 4, 9, 16], outcome
