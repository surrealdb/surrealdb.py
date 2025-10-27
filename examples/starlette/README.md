# Starlette + SurrealDB Example

A minimal async example demonstrating SurrealDB integration with Starlette, featuring CRUD operations, authentication, and WebSocket live queries.

## Features

- **Minimal & Fast**: Lightweight ASGI framework
- **Async/Await**: Full async support
- **CRUD Operations**: Complete user management API
- **Authentication**: Signup, signin, and session invalidation
- **Live Queries**: Real-time updates via WebSocket
- **Middleware**: CORS and error handling
- **Lifespan Management**: Proper database connection lifecycle

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
uv run uvicorn app:app --reload

# Production mode
uv run uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

### With pip

```bash
# Development mode with auto-reload
uvicorn app:app --reload

# Production mode
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`

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
starlette/
├── app.py               # Main application
├── config.py            # Configuration management
├── database.py          # Database connection
├── routes/              # Route handlers
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

- [Starlette Documentation](https://www.starlette.io/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [ASGI Specification](https://asgi.readthedocs.io/)

