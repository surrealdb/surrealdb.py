# Litestar + SurrealDB Example

A modern async example demonstrating SurrealDB integration with Litestar, featuring CRUD operations, authentication, DTOs, dependency injection, and WebSocket live queries.

## Features

- **Modern Async**: Built on ASGI with full async support
- **CRUD Operations**: Complete user management API
- **Authentication**: Signup, signin, and session invalidation
- **DTOs**: Type-safe data transfer objects
- **Dependency Injection**: Clean database connection management
- **Live Queries**: Real-time updates via WebSocket
- **Auto-generated Docs**: Interactive API documentation
- **Lifecycle Hooks**: Proper startup/shutdown management

## Prerequisites

- Python 3.10+
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

## Running the Application

### With uv (Recommended)

```bash
# Development mode with auto-reload
uv run litestar run --reload

# Production mode
uv run litestar run --host 0.0.0.0 --port 8000
```

### With pip

```bash
# Development mode with auto-reload
litestar run --reload

# Production mode
litestar run --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/schema
- **Redoc**: http://localhost:8000/schema/redoc
- **OpenAPI JSON**: http://localhost:8000/schema/openapi.json

## API Endpoints

### Users

- `POST /users` - Create a new user
- `GET /users` - List all users
- `GET /users/{user_id}` - Get user by ID
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user

### Authentication

- `POST /auth/signup` - Register a new account
- `POST /auth/signin` - Sign in to account
- `POST /auth/invalidate` - Sign out

### Live Queries

- `WS /ws/users` - Subscribe to real-time user updates

## Usage Examples

### Create a User

```bash
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
  }'
```

### Get All Users

```bash
curl "http://localhost:8000/users"
```

### WebSocket Live Queries

Connect to `ws://localhost:8000/ws/users` to receive real-time updates.

## Project Structure

```
litestar/
├── main.py              # Application entry point
├── config.py            # Configuration management
├── database.py          # Database connection
├── models.py            # DTOs and data models
├── controllers/         # Controller handlers
│   ├── __init__.py
│   ├── users.py         # User CRUD endpoints
│   ├── auth.py          # Authentication endpoints
│   └── websocket.py     # WebSocket live queries
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── docker-compose.yml   # SurrealDB setup
└── README.md           # This file
```

## Configuration

Environment variables (`.env`):

```
SURREALDB_URL=ws://localhost:8000/rpc
SURREALDB_NAMESPACE=test
SURREALDB_DATABASE=test
SURREALDB_USERNAME=root
SURREALDB_PASSWORD=root
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
# Format code
ruff format .

# Lint
ruff check .
```

## Learn More

- [Litestar Documentation](https://docs.litestar.dev/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [Litestar DTOs](https://docs.litestar.dev/latest/usage/dto/)

