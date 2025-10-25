# FastAPI + SurrealDB Example

A comprehensive example demonstrating SurrealDB integration with FastAPI, featuring CRUD operations, authentication, live queries, and modern async patterns.

## Features

- **CRUD Operations**: Complete user management API
- **Authentication**: Signup, signin, and session invalidation
- **Live Queries**: Real-time updates via WebSocket
- **Dependency Injection**: Clean database connection management
- **Auto-generated Docs**: Interactive OpenAPI documentation
- **Type Safety**: Full Pydantic model validation
- **Error Handling**: Comprehensive exception handling

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
uv run uvicorn main:app --reload

# Production mode
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### With pip

```bash
# Development mode with auto-reload
uvicorn main:app --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

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

### Update a User

```bash
curl -X PUT "http://localhost:8000/users/users:johndoe" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Updated",
    "email": "john.updated@example.com",
    "age": 31
  }'
```

### Sign Up

```bash
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "test",
    "database": "test",
    "access": "user",
    "email": "user@example.com",
    "password": "secure_password"
  }'
```

### WebSocket Live Queries

Connect to `ws://localhost:8000/ws/users` to receive real-time updates when users are created, updated, or deleted.

Example using JavaScript:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/users');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Live update:', data);
};
```

## Project Structure

```
fastapi/
├── main.py              # Application entry point
├── config.py            # Configuration management
├── database.py          # Database connection
├── models.py            # Pydantic models
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

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [Pydantic Documentation](https://docs.pydantic.dev/)

