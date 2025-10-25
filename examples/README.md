# SurrealDB Python SDK - Framework Examples

This directory contains comprehensive examples demonstrating how to integrate SurrealDB with popular Python frameworks. Each example is a standalone, production-ready application showcasing best practices and framework-specific patterns.

## Available Examples

### Web Frameworks

#### [FastAPI](./fastapi/)
**Modern async web framework with automatic API documentation**

- Full async/await support
- Pydantic model validation
- Dependency injection
- WebSocket live queries
- Auto-generated OpenAPI docs
- Type safety throughout

**Best for:** Modern API development, microservices, production applications

---

#### [Flask](./flask/)
**Traditional synchronous web framework with proven reliability**

- Sync database operations
- Blueprint organization
- Application factory pattern
- Request-scoped connections
- CORS support

**Best for:** Traditional web apps, legacy system integration, simpler projects

---

#### [Quart](./quart/)
**Async version of Flask with WebSocket support**

- Async Flask compatibility
- WebSocket live queries
- Blueprint organization
- Familiar Flask patterns

**Best for:** Flask users wanting async, WebSocket applications

---

#### [Starlette](./starlette/)
**Lightweight ASGI framework (FastAPI is built on this)**

- Minimal and fast
- Full async support
- WebSocket support
- Middleware system
- Lifespan management

**Best for:** Microservices, minimalist applications, learning ASGI

---

#### [Litestar](./litestar/)
**Modern async framework with advanced features**

- DTOs for type safety
- Dependency injection
- Guards and middleware
- WebSocket support
- Advanced lifecycle hooks
- Built-in validation

**Best for:** Enterprise applications, complex projects, type-safe APIs

---

#### [Sanic](./sanic/)
**High-performance async framework optimized for speed**

- Blazing fast
- Blueprint organization
- Listeners for lifecycle
- WebSocket support
- Multi-worker support

**Best for:** High-throughput APIs, real-time applications, performance-critical services

---

### AI & Integration

#### [FastMCP](./fastmcp/)
**Model Context Protocol server for AI assistants**

- MCP-compliant server
- Database tools for AI
- Resource handlers
- Claude Desktop integration
- Natural language database ops

**Best for:** AI assistant integration, Claude Desktop, LLM applications

---

#### [Django](./django/)
**Full-stack framework with Django REST Framework**

- Django REST Framework for APIs
- ViewSets and serializers
- Custom middleware
- Async views support
- DRF validation
- Admin interface ready

**Best for:** Full-stack applications, enterprise projects, teams familiar with Django

---

### Data & Exploration

#### [Jupyter Notebooks](./jupyter/)
**Interactive data exploration and analysis**

- 6 comprehensive notebooks
- CRUD operations tutorials
- Pandas DataFrame integration
- Data visualization (Matplotlib, Plotly)
- Live queries demonstrations
- Sample datasets included

**Best for:** Data exploration, learning, prototyping, analysis, teaching

---

### API Patterns

#### [GraphQL](./graphql/)
**Modern GraphQL server with Strawberry**

- Strawberry GraphQL (type-safe)
- Queries, mutations, subscriptions
- DataLoader for optimization
- WebSocket subscriptions
- GraphiQL playground
- Full async support

**Best for:** Modern APIs, mobile backends, flexible querying, real-time apps

---

## Common Features

All examples include:

- ✅ **CRUD Operations**: Complete user management
- ✅ **Authentication**: Signup, signin, invalidate
- ✅ **Docker Setup**: Ready-to-run SurrealDB instance
- ✅ **Environment Config**: Dotenv configuration
- ✅ **Error Handling**: Comprehensive exception handling
- ✅ **Documentation**: Detailed README with examples
- ✅ **Type Safety**: Modern Python type hints

Most async examples also include:

- ✅ **WebSocket Support**: Real-time live queries
- ✅ **Async/Await**: Modern async patterns
- ✅ **Connection Pooling**: Efficient resource management

## Quick Start

Each example follows the same setup pattern:

### Using uv (Recommended - Fast!)

```bash
# 1. Navigate to the example directory
cd examples/fastapi  # or any other framework

# 2. Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install dependencies
uv sync

# 4. Set up environment
cp .env.example .env

# 5. Start SurrealDB
docker compose up -d

# 6. Run the application
uv run uvicorn main:app --reload  # (varies by framework - see individual README)
```

### Using pip (Universal)

```bash
# 1. Navigate to the example directory
cd examples/fastapi  # or any other framework

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env

# 4. Start SurrealDB
docker compose up -d

# 5. Run the application
uvicorn main:app --reload  # (varies by framework - see individual README)
```

> **Why uv?** [uv](https://docs.astral.sh/uv/) is 10-100x faster than pip and is the modern standard for Python dependency management. It's what the main SurrealDB project uses!

## Choosing a Framework

### For Production APIs
- **First choice:** FastAPI (modern, well-documented, great DX)
- **Enterprise:** Litestar (advanced features, type safety)
- **High performance:** Sanic (speed-focused)

### For Traditional Web Apps
- **Flask** if you need sync operations or have existing Flask knowledge

### For Async Flask Users
- **Quart** for familiar patterns with async support

### For Minimalist Projects
- **Starlette** for lightweight, fast applications

### For AI Integration
- **FastMCP** for Claude Desktop and LLM integrations

## Project Structure

Each example follows a consistent structure:

```
framework-name/
├── README.md              # Detailed framework-specific docs
├── pyproject.toml        # Modern dependencies (uv)
├── requirements.txt       # Universal dependencies (pip)
├── .env.example          # Environment template
├── docker-compose.yml    # SurrealDB setup
├── config.py            # Configuration management
├── database.py          # Database connection
├── app.py or main.py    # Application entry point
└── routes/ or controllers/  # Organized handlers
```

Each example provides **both** `pyproject.toml` (for uv) and `requirements.txt` (for pip) so you can choose your preferred dependency management tool.

## API Endpoints

All examples (except FastMCP) expose similar REST endpoints:

### Users
- `POST /users` or `/api/users` - Create user
- `GET /users` or `/api/users` - List users
- `GET /users/{id}` - Get user by ID
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user

### Authentication
- `POST /auth/signup` or `/api/auth/signup` - Register
- `POST /auth/signin` or `/api/auth/signin` - Sign in
- `POST /auth/invalidate` or `/api/auth/invalidate` - Sign out

### Live Queries (WebSocket-enabled examples)
- `WS /ws/users` - Real-time user updates

## Database Setup

All examples use the same SurrealDB setup:

```yaml
# docker-compose.yml
services:
  surrealdb:
    image: surrealdb/surrealdb:v2.3.6
    ports:
      - "8000:8000"
    command: start --allow-all --user root --pass root
```

Default credentials:
- **URL:** `ws://localhost:8000/rpc`
- **Username:** `root`
- **Password:** `root`
- **Namespace:** `test`
- **Database:** `test`

⚠️ **Security Note:** These are development defaults. Always use secure credentials in production!

## Testing the Examples

### Basic Health Check
```bash
curl http://localhost:PORT/health
# or
curl http://localhost:PORT/
```

### Create a User
```bash
curl -X POST "http://localhost:PORT/users" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
  }'
```

### List Users
```bash
curl http://localhost:PORT/users
```

## Port Reference

Default ports for each framework:
- **FastAPI:** 8000
- **Flask:** 5000
- **Quart:** 5000
- **Starlette:** 8000
- **Litestar:** 8000
- **Sanic:** 8000
- **FastMCP:** stdio (no HTTP port)

## WebSocket Testing

For examples with WebSocket support, you can test using:

### Python
```python
import asyncio
import websockets
import json

async def test_websocket():
    async with websockets.connect('ws://localhost:8000/ws/users') as ws:
        async for message in ws:
            print(json.loads(message))

asyncio.run(test_websocket())
```

### JavaScript
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/users');
ws.onmessage = (event) => {
  console.log(JSON.parse(event.data));
};
```

## Contributing

When adding new examples:

1. Follow the existing structure
2. Include comprehensive README
3. Add docker-compose.yml
4. Provide .env.example
5. Implement all common features
6. Add framework-specific best practices
7. Update this main README

## Learn More

- [SurrealDB Documentation](https://surrealdb.com/docs)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [SurrealDB GitHub](https://github.com/surrealdb/surrealdb)

## License

All examples are provided under the same license as the main SurrealDB Python SDK (Apache 2.0).

