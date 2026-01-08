# Logfire + SurrealDB Example

A comprehensive example demonstrating automatic observability for SurrealDB operations using Pydantic Logfire. This example shows how to instrument your SurrealDB connections to get instant visibility into database operations.

## What is Logfire?

[Pydantic Logfire](https://docs.pydantic.dev/logfire/) is an observability platform built by the creators of Pydantic. It provides:

- **Automatic instrumentation** for popular Python libraries including SurrealDB
- **OpenTelemetry compatibility** - works with any OTel-compatible platform
- **Smart defaults** - automatically scrubs sensitive data
- **Beautiful dashboards** - purpose-built for Python applications
- **Zero configuration** - works out of the box for local development

## Features Demonstrated

- **Automatic span creation**: Every database operation creates a trace span
- **Smart parameter logging**: Query parameters and data logged (with sensitive data scrubbed)
- **All connection types**: Works with HTTP, WebSocket, and embedded databases
- **CRUD operations**: Create, Read, Update, Delete all instrumented
- **Authentication**: Signin, signup, invalidate operations traced
- **Query operations**: Raw SurrealQL queries with automatic logging
- **Error tracking**: Exceptions and errors captured in spans

## Prerequisites

- Python 3.9+
- Docker (for running SurrealDB)

## Installation

### Option 1: Using uv (Recommended - Fast!)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Copy environment file
cp .env.example .env

# Start SurrealDB
docker compose up -d
```

### Option 2: Using pip (Universal)

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Start SurrealDB
docker compose up -d
```

## Running the Example

### With uv (Recommended)

```bash
# Run the example
uv run python main.py
```

### With pip

```bash
# Run the example
python main.py
```

## What You'll See

The example performs various database operations, each creating a span in the trace:

```
🔧 Configuring Logfire...
📡 Instrumenting SurrealDB...
🔌 Connecting to database...
✅ Connected to SurrealDB

Logfire is now tracing all SurrealDB operations!
Each operation below creates a span with details about the database call.

👤 Signing in...
🗂️  Using namespace and database...
➕ Creating users...
📖 Selecting all users...
🔍 Querying users with SurrealQL...
✏️  Updating user...
🗑️  Deleting user...
🧹 Cleaning up...

✨ Done! Check your terminal or Logfire dashboard for traces.
```

## Expected Output

Console output shows each operation with timing information:

```
surrealdb signin username = root ⏱️ 15.2ms
surrealdb use namespace = test, database = test ⏱️ 2.1ms
surrealdb create ⏱️ 8.3ms
surrealdb select ⏱️ 3.2ms
surrealdb query ⏱️ 4.7ms
surrealdb update ⏱️ 5.1ms
surrealdb delete ⏱️ 3.8ms
```

Each line represents a span with:
- **Operation name**: The database method called
- **Parameters**: Non-sensitive parameters (passwords/tokens scrubbed)
- **Duration**: How long the operation took

## Understanding the Traces

### Span Naming Convention

Logfire creates spans with names like:
- `surrealdb signin` - Authentication operations
- `surrealdb use` - Namespace/database selection
- `surrealdb create` - Record creation
- `surrealdb select` - Record selection
- `surrealdb query` - Raw SurrealQL queries
- `surrealdb update` - Record updates
- `surrealdb delete` - Record deletion

### Span Attributes

Each span includes attributes such as:
- `namespace` - The SurrealDB namespace
- `database` - The database name
- `record` - The record ID or table name
- Non-sensitive parameters passed to the operation

### Sensitive Data Scrubbing

Logfire automatically scrubs:
- Passwords
- Tokens
- Authentication credentials
- Any parameter containing "password", "token", "secret", etc.

## Configuration

### Environment Variables

Edit `.env` to configure:

```bash
# SurrealDB Configuration
SURREALDB_URL=ws://localhost:8000/rpc
SURREALDB_NAMESPACE=test
SURREALDB_DATABASE=test
SURREALDB_USERNAME=root
SURREALDB_PASSWORD=root

# Logfire Configuration (Optional)
# LOGFIRE_TOKEN=your_token_here  # For sending to Logfire cloud
```

### Logfire Dashboard Setup

For cloud-based tracing (optional):

1. **Create a Logfire account** at [logfire.pydantic.dev](https://logfire.pydantic.dev)
2. **Get your token** from the dashboard
3. **Set the environment variable**: `LOGFIRE_TOKEN=your_token_here`
4. **Run the example** - traces will appear in your dashboard

For local development, Logfire works without a token and displays traces in the console.

## Instrumentation Options

### Instrument All Connection Classes

```python
import logfire
from surrealdb import AsyncSurreal

# Instrument all SurrealDB connections globally
logfire.configure()
logfire.instrument_surrealdb()

# All instances are now instrumented
db1 = AsyncSurreal("ws://localhost:8000")
db2 = AsyncSurreal("http://localhost:8000")
```

### Instrument Specific Instance

```python
import logfire
from surrealdb import AsyncSurreal

logfire.configure()

# Create connection
db = AsyncSurreal("ws://localhost:8000")

# Instrument just this instance
logfire.instrument_surrealdb(db)
```

### Instrument Specific Connection Class

```python
import logfire
from surrealdb.connections import AsyncHttpSurrealConnection

logfire.configure()

# Instrument only HTTP connections
logfire.instrument_surrealdb(AsyncHttpSurrealConnection)
```

## Advanced Usage

### Custom Logfire Configuration

```python
import logfire

# Configure with custom settings
logfire.configure(
    service_name="my-surrealdb-app",
    service_version="1.0.0",
    environment="production",
    console=True,  # Show traces in console
)

logfire.instrument_surrealdb()
```

### Adding Custom Spans

```python
import logfire
from surrealdb import AsyncSurreal

logfire.configure()
logfire.instrument_surrealdb()

async with AsyncSurreal("ws://localhost:8000") as db:
    # Custom span for business logic
    with logfire.span("user-registration-flow"):
        await db.signin({"username": "root", "password": "root"})
        await db.use("test", "test")
        
        # These database operations are nested within your custom span
        user = await db.create("user", {"email": "user@example.com"})
        await db.create("profile", {"user_id": user["id"]})
```

### Filtering Operations

You can selectively instrument operations:

```python
import logfire
from surrealdb import AsyncSurreal

# Only instrument, then manually control what gets traced
logfire.configure(console={"min_log_level": "info"})
logfire.instrument_surrealdb()
```

## Project Structure

```
logfire/
├── main.py              # Demo application
├── config.py            # Configuration management
├── database.py          # Database and instrumentation setup
├── requirements.txt     # Python dependencies (pip)
├── pyproject.toml       # Modern dependencies (uv)
├── .env.example         # Environment template
├── docker-compose.yml   # SurrealDB setup
└── README.md           # This file
```

## Troubleshooting

### No traces appearing

**Problem**: Operations execute but no trace output appears.

**Solution**: 
- Ensure `logfire.configure()` is called before operations
- Check that `logfire.instrument_surrealdb()` is called after configure
- Try `logfire.configure(console=True)` to force console output

### Sensitive data appearing in logs

**Problem**: Passwords or tokens visible in traces.

**Solution**: Logfire should automatically scrub these. If not:
- Report an issue to Pydantic Logfire
- Use custom scrubbing rules in `logfire.configure()`

### Performance concerns

**Problem**: Worried about instrumentation overhead.

**Solution**:
- Logfire overhead is minimal (<1ms per operation typically)
- Can be disabled in production with environment variable
- Sampling can be configured to reduce overhead

### Connection to Logfire cloud fails

**Problem**: Cannot send traces to Logfire dashboard.

**Solution**:
- Check `LOGFIRE_TOKEN` is set correctly
- Verify network connectivity
- For local development, console output works without token

## Integration with Other Tools

### Using with OpenTelemetry Collectors

Logfire exports standard OpenTelemetry data:

```python
import logfire

logfire.configure(
    # Export to OTLP collector
    otlp_endpoint="http://localhost:4317"
)
```

### Using with Jaeger

```python
import logfire

logfire.configure(
    # Jaeger endpoint
    otlp_endpoint="http://localhost:14268/api/traces"
)
```

### Using with DataDog, Honeycomb, etc.

All OpenTelemetry-compatible platforms work with Logfire's output.

## Learn More

- [Logfire Documentation](https://docs.pydantic.dev/logfire/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Logfire SurrealDB Integration Source](https://github.com/pydantic/logfire/blob/main/logfire/_internal/integrations/surrealdb.py)

## Why Use Observability?

Observability helps you:

- **Debug issues faster**: See exactly what database operations occurred
- **Find performance bottlenecks**: Identify slow queries
- **Track down errors**: See the full context when operations fail
- **Monitor production**: Understand database usage patterns
- **Optimize queries**: See which operations are most expensive

## Next Steps

1. **Run this example** to see instrumentation in action
2. **Add to your project**: Use the same pattern in your application
3. **Explore Logfire dashboard**: Sign up for cloud tracing
4. **Customize instrumentation**: Add custom spans for your business logic
5. **Set up alerts**: Get notified of slow queries or errors
