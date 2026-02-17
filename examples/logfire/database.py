"""Database setup with Logfire instrumentation."""

import logfire
from surrealdb import AsyncSurreal

from config import config


def setup_logfire() -> None:
    """Configure and initialize Logfire instrumentation.

    This sets up Logfire with appropriate settings and instruments
    all SurrealDB operations for automatic tracing.
    """
    print("🔧 Configuring Logfire...")

    # Configure Logfire
    # If LOGFIRE_TOKEN is set, traces will be sent to Logfire cloud
    # Otherwise, traces will be displayed in the console
    logfire_config = {
        "service_name": "surrealdb-logfire-example",
        "console": True,  # Always show traces in console
    }

    if config.logfire_token:
        logfire_config["token"] = config.logfire_token
        print("   📤 Traces will be sent to Logfire cloud")
    else:
        print("   💻 Traces will be displayed in console only")

    logfire.configure(**logfire_config)

    # Instrument SurrealDB
    # This enables automatic tracing for all SurrealDB operations
    print("📡 Instrumenting SurrealDB...")
    logfire.instrument_surrealdb()

    print("   ✅ All SurrealDB operations will now be traced\n")


async def get_database() -> AsyncSurreal:
    """Create and return a configured database connection.

    Returns:
        AsyncSurreal: Configured database connection
    """
    print("🔌 Connecting to database...")

    # Create database connection
    db = AsyncSurreal(config.surrealdb_url)

    # Connect (note: AsyncSurreal with context manager auto-connects,
    # but we're doing it explicitly here for demonstration)
    await db.connect()

    # Sign in with root credentials
    await db.signin(
        {
            "username": config.surrealdb_username,
            "password": config.surrealdb_password,
        },
    )

    # Select namespace and database
    await db.use(config.surrealdb_namespace, config.surrealdb_database)

    print("✅ Connected to SurrealDB\n")

    return db
