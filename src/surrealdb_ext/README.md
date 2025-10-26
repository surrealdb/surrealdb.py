# Embedded SurrealDB Implementation

This document describes the PyO3-based embedded SurrealDB implementation for the Python SDK.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [URL Schemes](#url-schemes)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Implementation Details](#implementation-details)
- [Build System](#build-system)
- [Performance](#performance)
- [Limitations](#limitations)
- [Testing](#testing)
- [Future Enhancements](#future-enhancements)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [FAQ](#faq)
- [Resources](#resources)

## Overview

The embedded database feature allows SurrealDB to run directly within your Python application without requiring a separate server process. This is implemented using PyO3, which provides Rust-Python bindings, giving you access to the full SurrealDB engine compiled as a native extension.

### Key Features

- **No server required**: Database runs directly in your Python process
- **Multiple storage backends**: In-memory (`memory` or `mem://`) and file-based (`file://` or `surrealkv://`) options
- **Full API compatibility**: Works with all SDK methods (query, select, create, update, etc.)
- **Async and sync support**: Both `AsyncSurreal` and `Surreal` APIs available
- **Cross-platform**: Pre-built wheels for Linux, macOS, and Windows
- **Python 3.9+**: Supports Python 3.9, 3.10, 3.11, 3.12, and 3.13

## Architecture

### Components

```
┌─────────────────────────────────────────┐
│         Python Application              │
├─────────────────────────────────────────┤
│  AsyncSurreal / Surreal                 │
│  (Factory Functions)                    │
├─────────────────────────────────────────┤
│  AsyncEmbeddedSurrealConnection         │
│  BlockingEmbeddedSurrealConnection      │
│  (Python Wrapper Classes)               │
├─────────────────────────────────────────┤
│  _surrealdb_ext                         │
│  (Rust Extension Module)                │
│  ┌───────────────────────────────────┐  │
│  │ AsyncEmbeddedDB                   │  │
│  │ SyncEmbeddedDB                    │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  SurrealDB Core (Rust)                  │
│  - In-Memory Storage (kv-mem)           │
│  - SurrealKV Storage (kv-surrealkv)     │
└─────────────────────────────────────────┘
```

### Key Files

**Build Configuration:**
- `pyproject.toml` - Maturin build backend configuration
- `Cargo.toml` - Rust dependencies and build settings

**Rust Extension (`src/surrealdb_ext/`):**
- `lib.rs` - Module entry point
- `async_db.rs` - Async database implementation
- `sync_db.rs` - Blocking database implementation
- `types.rs` - Python ↔ Rust type conversions
- `errors.rs` - Error mapping

**Python Connections (`src/surrealdb/connections/`):**
- `async_embedded.py` - AsyncTemplate implementation
- `blocking_embedded.py` - SyncTemplate implementation
- `url.py` - URL scheme handling (MEM, FILE)

**Type Stubs:**
- `src/surrealdb/_surrealdb_ext.pyi` - Type hints for Rust extension

## URL Schemes

The SDK supports four connection types through URL schemes:

| Scheme | Type | Description | Example | Use Case |
|--------|------|-------------|---------|----------|
| `ws://`, `wss://` | Remote | WebSocket connection | `ws://localhost:8000/rpc` | Production, multi-client |
| `http://`, `https://` | Remote | HTTP connection | `http://localhost:8000` | REST-like access |
| `memory`, `mem://` | Embedded | In-memory database | `memory` or `mem://` | Testing, caching |
| `file://`, `surrealkv://` | Embedded | File-based database | `file://mydb` or `surrealkv://mydb` | Local apps, development |

**Note:** Embedded databases (`memory`, `mem://`, `file://`, and `surrealkv://`) use the native Rust extension and don't require a separate SurrealDB server.

### Embedded vs Remote: Which Should You Use?

**Choose Embedded (`memory`, `mem://`, `file://`, or `surrealkv://`) when:**
- ✅ Building desktop/CLI applications
- ✅ Running unit tests (in-memory is extremely fast)
- ✅ Local development without Docker/server setup
- ✅ Single-process applications
- ✅ Edge computing or offline-first apps
- ✅ Prototyping and experimentation

**Choose Remote (`ws://` or `http://`) when:**
- ✅ Multiple services need to share data
- ✅ Building distributed systems or microservices
- ✅ Need live queries and subscriptions
- ✅ Horizontal scaling across multiple nodes
- ✅ Production web applications with multiple clients
- ✅ Team collaboration with shared database

**Feature Comparison:**

| Feature | Embedded | Remote |
|---------|----------|--------|
| Server required | ❌ No | ✅ Yes |
| Setup complexity | Low | Medium |
| Live queries | ❌ No | ✅ Yes |
| Clustering | ❌ No | ✅ Yes |
| Multi-client | ❌ Single process | ✅ Yes |
| Network latency | None | Depends on connection |
| Installation | Just `pip install` | Docker/binary + SDK |

## Quick Start

### Installation

```bash
# Install from PyPI (includes pre-built wheels)
pip install surrealdb

# or using uv
uv add surrealdb
```

No additional setup required! The embedded database functionality is included by default.

### 30-Second Example

```python
from surrealdb import Surreal

# Create an in-memory database - no server needed!
with Surreal("memory") as db:
    db.use("test", "test")
    db.signin({"username": "root", "password": "root"})
    
    # Create a record
    person = db.create("person", {"name": "Alice", "age": 30})
    print(f"Created: {person}")
    
    # Query it back
    people = db.select("person")
    print(f"Found: {people}")
```

That's it! No Docker, no server setup, just Python + SurrealDB.

## Usage

### Async API

```python
import asyncio
from surrealdb import AsyncSurreal

async def main():
    # In-memory database (can use "memory" or "mem://")
    async with AsyncSurreal("memory") as db:
        await db.use("test", "test")
        await db.signin({"username": "root", "password": "root"})
        
        result = await db.create("person", {"name": "Alice"})
        print(result)
    
    # File-based database
    async with AsyncSurreal("file://mydb") as db:
        await db.use("test", "test")
        await db.signin({"username": "root", "password": "root"})
        
        result = await db.query("SELECT * FROM person")
        print(result)

asyncio.run(main())
```

### Blocking API

```python
from surrealdb import Surreal

# In-memory database (can use "memory" or "mem://")
with Surreal("memory") as db:
    db.use("test", "test")
    db.signin({"username": "root", "password": "root"})
    
    result = db.create("person", {"name": "Bob"})
    print(result)
```

## Implementation Details

### Rust Extension

**AsyncEmbeddedDB:**
- Uses `pyo3-asyncio` to bridge Tokio and Python's asyncio
- All async methods return Python futures
- Proper GIL management for I/O operations

**SyncEmbeddedDB:**
- Wraps async operations with `tokio::runtime::Runtime`
- Blocks on async operations to provide synchronous API
- Each instance maintains its own Tokio runtime

**Type Conversions:**

The extension handles bidirectional type conversion between Python and Rust:

| Python Type | Rust Type | Notes |
|-------------|-----------|-------|
| `dict` | `serde_json::Value::Object` | For query parameters and results |
| `list` | `serde_json::Value::Array` | Supports nested arrays |
| `str` | `String` | UTF-8 strings |
| `int` | `i64` | Signed 64-bit integers |
| `float` | `f64` | 64-bit floats |
| `bool` | `bool` | True/False |
| `None` | `Null` | Python None ↔ JSON null |
| `bytes` | `Vec<u8>` | Binary data via CBOR |

**Error Handling:**
- Rust errors are converted to Python exceptions
- Maintains full error context and messages
- All SurrealDB errors propagate correctly to Python

### Storage Backends

The embedded database supports two storage backends, configured via the Cargo.toml features:

**In-Memory (`memory` or `mem://`) - kv-mem feature:**
- Data stored entirely in RAM
- Extremely fast operations (microsecond latency)
- Non-persistent - data cleared when connection closes
- No disk I/O overhead
- **Best for:** Unit tests, temporary caches, development prototyping

**File-Based (`file://` or `surrealkv://`) - kv-surrealkv feature:**
- Uses SurrealKV storage engine (SurrealDB's custom storage layer)
- Data persists to disk automatically
- ACID compliant with transaction support
- Good performance with optimized disk I/O
- **Best for:** Desktop applications, local development, embedded systems

**Backend Comparison:**

| Feature | `memory`/`mem://` | `file://`/`surrealkv://` |
|---------|----------|-----------|
| Persistence | ❌ No | ✅ Yes |
| Speed | ⚡ Fastest | 🚀 Fast |
| Disk usage | None | ~Few MB + data |
| ACID | ✅ Yes | ✅ Yes |
| Concurrent access | Single process | Single process |

## Build System

### Requirements

**For using pre-built wheels (recommended):**
- Python 3.9 or later
- pip or uv package manager
- Compatible platform (Linux x86_64/aarch64, macOS x86_64/arm64, Windows x64)

**For building from source:**
- All of the above, plus:
- Rust toolchain (1.70 or later): https://rustup.rs/
- C compiler (gcc, clang, or MSVC)
- maturin: `pip install maturin` or `uv add maturin --dev`

### Development Build

```bash
# Install maturin
pip install maturin
# or using uv
uv add maturin --dev

# Build and install in development mode (editable install)
maturin develop --release

# or with uv
uv run maturin develop --release
```

**Note:** The `--release` flag is important for performance! Debug builds can be 10-100x slower.

### Production Wheels

```bash
# Build wheel for current platform
maturin build --release

# Build for specific Python versions
maturin build --release --interpreter python3.9 python3.10 python3.11 python3.12 python3.13
```

### CI/CD

The `.github/workflows/build.yml` workflow automatically builds wheels on releases:

**Linux (manylinux):**
- x86_64 (Intel/AMD 64-bit)
- aarch64 (ARM 64-bit)

**macOS:**
- x86_64 (Intel Macs)
- aarch64 (Apple Silicon M1/M2/M3)

**Windows:**
- x64

**Python versions:** 3.9, 3.10, 3.11, 3.12, and 3.13

Wheels use **ABI3** (stable ABI), meaning a single wheel works across all supported Python versions on the same platform.

## Performance

### GIL Handling

- All I/O operations release the GIL
- Allows true parallelism with Python threads
- No blocking of other Python code during database operations

### Memory

- Rust code uses Arc/Mutex for thread-safe sharing
- Python reference counting integrated with PyO3
- Automatic cleanup via Drop trait

## Limitations

### Currently Not Implemented

The following features are not yet available for embedded databases:

| Feature | Status | Workaround |
|---------|--------|------------|
| Live queries (`live()`, `subscribe_live()`) | ❌ Not implemented | Use polling with `select()` or connect to remote DB |
| Advanced authentication | ⚠️ Partial - only root signin | Use root credentials for embedded |
| User signup (`signup()`) | ❌ Not implemented | Pre-create users or use root access |
| Session info (`info()`) | ❌ Not implemented | Track session data in application |
| Multi-node clustering | ❌ Not supported | Use remote SurrealDB server for clustering |
| Network-based replication | ❌ Not supported | Embedded is single-process only |

**Note:** These limitations are specific to embedded mode. Remote connections (WebSocket/HTTP) support all features.

### Known Caveats

1. **Binary size**: Wheels are large (~50-100 MB) due to including the full SurrealDB engine
2. **Build time**: Source builds require Rust toolchain (rustc, cargo) and take 5-10 minutes
3. **Platform specific**: Must use correct wheel for your OS and architecture
4. **Memory usage**: Each embedded instance maintains its own Tokio runtime (minimal overhead)
5. **First import delay**: Initial import may take 1-2 seconds while loading the native extension

## Testing

### Unit Tests

Run embedded database tests:

```bash
# All embedded tests
pytest tests/unit_tests/connections/embedded/

# Async tests only
pytest tests/unit_tests/connections/embedded/test_async_embedded.py

# Blocking tests only
pytest tests/unit_tests/connections/embedded/test_blocking_embedded.py

# File persistence tests
pytest tests/unit_tests/connections/embedded/test_file_persistence.py
```

### Examples

Run example scripts:

```bash
# Async in-memory example
python examples/embedded/basic_async.py

# Sync in-memory example
python examples/embedded/basic_sync.py

# File-based persistence example
python examples/embedded/persistence.py
```

## Future Enhancements

Potential improvements for future versions:

1. **Live query support**: Implement background task management for notifications
2. **Additional storage backends**: RocksDB, TiKV support
3. **Advanced authentication**: Full scope-based authentication
4. **Better error messages**: More detailed error context from Rust
5. **Custom type support**: Better handling of SurrealDB-specific types (Duration, Geometry, etc.)
6. **Startup options**: Configuration for memory limits, storage paths, etc.
7. **Metrics and monitoring**: Expose database metrics to Python

## Troubleshooting

### Build Issues

**Problem**: `maturin` not found
```bash
pip install maturin
# or
uv add maturin --dev
```

**Problem**: Rust toolchain not installed
```bash
# Install Rust using rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# Then restart your shell
```

**Problem**: Build fails with linker errors
- **Linux**: Install build-essential: `sudo apt-get install build-essential`
- **macOS**: Install Xcode Command Line Tools: `xcode-select --install`
- **Windows**: Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) with C++ workload

**Problem**: Build succeeds but takes very long
- This is normal! Building SurrealDB from source takes 5-10 minutes
- Use `--release` flag for optimized builds (slower but much faster runtime)
- Consider using pre-built wheels from PyPI instead

### Runtime Issues

**Problem**: `ImportError: cannot import name '_surrealdb_ext'`
```bash
# For development builds, ensure you've built the extension:
maturin develop --release
# or use uv:
uv run maturin develop --release

# For pip installs, ensure you have the correct wheel for your platform
pip install --force-reinstall surrealdb
```

**Problem**: `ModuleNotFoundError: No module named 'surrealdb._surrealdb_ext'`
- The native extension wasn't installed properly
- Check you're using the right Python version (3.9+)
- Verify platform compatibility (wheels available for Linux, macOS, Windows)

**Problem**: Database connection errors with embedded database
```python
# ❌ Wrong - missing use()
async with AsyncSurreal("memory") as db:
    await db.create("person", {...})  # Error!

# ✅ Correct - must call use() first
async with AsyncSurreal("memory") as db:
    await db.use("test", "test")
    await db.signin({"username": "root", "password": "root"})
    await db.create("person", {...})  # Works!
```

**Problem**: File-based database permission errors
- Ensure the path exists or can be created
- Check write permissions for the directory
- Use absolute paths to avoid confusion: `file:///absolute/path/to/db`

**Problem**: Performance is slower than expected
- Use `memory` (or `mem://`) instead of `file://` for maximum speed
- Release GIL operations: ensure you're using async properly
- First query is slower (runtime initialization), subsequent queries are fast

**Problem**: "Database does not exist" error
- You must call `.use(namespace, database)` before any queries
- Both namespace and database are required, even for embedded databases

## Contributing

When contributing to embedded database functionality:

### Making Changes

1. **Rust changes** (in `src/surrealdb_ext/`):
   - `lib.rs` - Module definition and PyO3 setup
   - `async_db.rs` - Async database implementation
   - `sync_db.rs` - Blocking database implementation
   - `errors.rs` - Error type conversions

2. **Rebuild after Rust changes**:
   ```bash
   uv run maturin develop --release
   ```

3. **Python wrapper changes** (in `src/surrealdb/connections/`):
   - `async_embedded.py` - AsyncSurreal implementation
   - `blocking_embedded.py` - Surreal implementation

4. **Add tests** in `tests/unit_tests/connections/embedded/`:
   - Test both async and sync variants
   - Test both memory and file:// backends
   - Include error cases

5. **Update type stubs** in `src/surrealdb/_surrealdb_ext.pyi`:
   - Add type hints for new Rust methods
   - Keep in sync with Rust implementation

### Testing Your Changes

```bash
# Run embedded tests only
pytest tests/unit_tests/connections/embedded/

# Run with coverage
pytest tests/unit_tests/connections/embedded/ --cov=src/surrealdb --cov-report=term

# Run a specific test file
pytest tests/unit_tests/connections/embedded/test_async_embedded.py -v
```

### Code Quality

```bash
# Format Python code
uv run ruff format src/

# Lint Python code
uv run ruff check src/

# Type check
uv run mypy src/

# Format Rust code
cd src/surrealdb_ext && cargo fmt

# Lint Rust code
cd src/surrealdb_ext && cargo clippy
```

## FAQ

### General Questions

**Q: Do I need to install Rust to use the embedded database?**

A: No! Pre-built wheels are available on PyPI for all major platforms. Just `pip install surrealdb` and it works. Rust is only needed if building from source.

**Q: What's the difference between `memory` (or `mem://`) and `file://` (or `surrealkv://`)?**

A: `memory`/`mem://` stores data in RAM (fast, non-persistent), while `file://`/`surrealkv://` stores data on disk (persistent, good performance). Use `memory` for tests/caches, `file://` for apps that need persistence.

**Q: Can I use embedded and remote databases in the same application?**

A: Yes! You can connect to both embedded and remote databases simultaneously. Just create separate connection instances with different URLs.

**Q: Is the embedded database thread-safe?**

A: Yes, but each connection instance is designed for single-process use. For multi-threaded apps, create separate connections or use proper synchronization.

**Q: How big is the installed package?**

A: The wheel is ~50-100 MB, installed size is ~100-200 MB. This includes the full SurrealDB engine. If size is critical, consider using a remote database instead.

### Performance Questions

**Q: Is embedded mode faster than remote?**

A: For single-process applications, yes! Embedded has zero network latency. However, remote databases can scale horizontally and handle multiple clients efficiently.

**Q: Why is the first query slow?**

A: The Tokio runtime initializes on first use. Subsequent queries are much faster. This is a one-time cost per connection.

**Q: Does the embedded database release the GIL?**

A: Yes! All I/O operations release Python's GIL, allowing true parallelism with threads.

### Development Questions

**Q: Do I need to rebuild after every code change?**

A: Only after Rust code changes. Python changes (connection classes, etc.) work immediately. Run `uv run maturin develop --release` after Rust changes.

**Q: Why does my build take so long?**

A: SurrealDB is a large Rust codebase. First build takes 5-10 minutes. Incremental builds are faster (~1-2 minutes). Use `--release` for optimized builds.

**Q: Can I debug Rust code?**

A: Yes! Use `maturin develop` (without `--release`) for debug builds with symbols. Then use `lldb` (macOS/Linux) or Visual Studio debugger (Windows).

### Compatibility Questions

**Q: What Python versions are supported?**

A: Python 3.9, 3.10, 3.11, 3.12, and 3.13. Wheels use the stable ABI (ABI3) so one wheel works for all versions.

**Q: What platforms are supported?**

A: Linux (x86_64, aarch64), macOS (Intel, Apple Silicon), and Windows (x64). Pre-built wheels are available for all.

**Q: Can I use this with PyPy or other Python implementations?**

A: Currently only CPython is supported due to PyO3's requirements. PyPy support may come in the future.

## Resources

- [PyO3 Documentation](https://pyo3.rs/)
- [Maturin Guide](https://www.maturin.rs/)
- [SurrealDB Rust SDK](https://docs.rs/surrealdb/)
- [Python SDK Documentation](https://surrealdb.com/docs/sdk/python)

