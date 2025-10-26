# Embedded SurrealDB Examples

This directory contains examples of using SurrealDB embedded directly within Python applications.

## Examples

### `basic_async.py`

Demonstrates basic async operations with an in-memory embedded database:
- Creating an in-memory database with `mem://` (or `memory`)
- Basic CRUD operations (Create, Read, Update, Delete)
- Running SurrealQL queries
- Using context managers for automatic cleanup

Run with:
```bash
python examples/embedded/basic_async.py
```

### `basic_sync.py`

Shows the same operations as `basic_async.py` but using the blocking/synchronous API:
- Synchronous operations with `Surreal` instead of `AsyncSurreal`
- All the same database operations without `await`
- Perfect for scripts and simple applications

Run with:
```bash
python examples/embedded/basic_sync.py
```

### `persistence.py`

Demonstrates file-based persistent storage:
- Using `file://` (or `surrealkv://`) URLs for persistent databases
- Data persisting across multiple connections
- Updating persisted data
- Using temporary directories for testing

Run with:
```bash
python examples/embedded/persistence.py
```

## When to Use Embedded vs Remote

### Use Embedded Database (`memory`, `mem://`, `file://`, or `surrealkv://`) when:

- **Desktop Applications**: No server setup required
- **Testing**: In-memory databases are extremely fast for tests
- **Local Development**: Quick prototyping without infrastructure
- **Edge Computing**: Running on devices without network access
- **Single-App Storage**: Application-specific data storage

### Use Remote Database (`ws://` or `http://`) when:

- **Multi-App Architecture**: Multiple applications sharing data
- **Distributed Systems**: Microservices or distributed architectures
- **Cloud Deployments**: Scalable cloud infrastructure
- **Horizontal Scaling**: Need to scale across multiple instances
- **Team Collaboration**: Centralized data for multiple developers

## Performance Considerations

### In-Memory (`memory` or `mem://`)
- **Fastest**: All data in RAM
- **Non-persistent**: Data lost when connection closes
- **Best for**: Tests, caches, temporary data

### File-Based (`file://` or `surrealkv://`)
- **Persistent**: Data saved to disk
- **Good performance**: SurrealKV storage engine
- **Best for**: Local apps, development, single-node deployments

## Installation Note

The embedded database functionality is included in the standard `surrealdb` package:

```bash
pip install surrealdb
```

Pre-built wheels are available for:
- Linux (x86_64, aarch64)
- macOS (x86_64, ARM64)
- Windows (x64)

For Python 3.9, 3.10, 3.11, 3.12, and 3.13.

