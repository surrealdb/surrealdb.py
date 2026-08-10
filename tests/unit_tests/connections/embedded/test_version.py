"""Tests that embedded connections report the SurrealDB engine version."""

from surrealdb import AsyncSurreal, Surreal

# The engine floor is the `surrealdb-core = "3"` requirement in
# embedded/Cargo.toml narrowed to the minor series currently resolved. It is
# deliberately not compared against the extension's own version: the SDK line
# and the engine line both track SurrealDB majors, so they will eventually
# collide on the same number and an inequality would fail bafflingly.
MINIMUM_ENGINE_VERSION = (3, 2)


def _assert_engine_version(version: str) -> None:
    assert version.startswith("surrealdb-"), version
    engine = version.removeprefix("surrealdb-")
    major, minor = engine.split(".")[:2]
    assert (int(major), int(minor)) >= MINIMUM_ENGINE_VERSION, version


def test_blocking_version_reports_engine() -> None:
    """The blocking embedded connection reports the linked engine version."""
    with Surreal("mem://") as db:
        db.use("test", "test")

        _assert_engine_version(db.version())


async def test_async_version_reports_engine() -> None:
    """The async embedded connection reports the linked engine version."""
    async with AsyncSurreal("mem://") as db:
        await db.use("test", "test")

        _assert_engine_version(await db.version())
