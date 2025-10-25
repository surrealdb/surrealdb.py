# Quart + SurrealDB Example

A comprehensive example demonstrating SurrealDB integration with Quart (async Flask), featuring CRUD operations, authentication, and WebSocket live queries.

## Features

- **Async/Await**: Full async support throughout
- **CRUD Operations**: Complete user management API
- **Authentication**: Signup, signin, and session invalidation
- **Live Queries**: Real-time updates via WebSocket
- **Blueprints**: Organized route handlers
- **CORS Support**: Ready for frontend integration
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
uv run quart run --debug

# Or using hypercorn directly
uv run hypercorn app:create_app --reload

# Production mode
uv run hypercorn app:create_app --bind 0.0.0.0:5000
```

### With pip

```bash
# Development mode with auto-reload
quart run --debug

# Or using hypercorn directly
hypercorn app:create_app --reload

# Production mode
hypercorn app:create_app --bind 0.0.0.0:5000
```

The API will be available at `http://localhost:5000`

## API Endpoints

### Users

- `POST /api/users` - Create a new user
- `GET /api/users` - List all users
- `GET /api/users/<user_id>` - Get user by ID
- `PUT /api/users/<user_id>` - Update user
- `DELETE /api/users/<user_id>` - Delete user

### Authentication

- `POST /api/auth/signup` - Register a new account
- `POST /api/auth/signin` - Sign in to account
- `POST /api/auth/invalidate` - Sign out

### Live Queries

- `WS /ws/users` - Subscribe to real-time user updates

## Usage Examples

### Create a User

```bash
curl -X POST "http://localhost:5000/api/users" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
  }'
```

### Get All Users

```bash
curl "http://localhost:5000/api/users"
```

### WebSocket Live Queries

Connect to `ws://localhost:5000/ws/users` to receive real-time updates.

Example using Python:
```python
import asyncio
import websockets
import json

async def listen():
    async with websockets.connect('ws://localhost:5000/ws/users') as ws:
        async for message in ws:
            data = json.loads(message)
            print('Live update:', data)

asyncio.run(listen())
```

## Project Structure

```
quart/
├── app.py               # Application factory
├── config.py            # Configuration management
├── database.py          # Database connection
├── routes/              # Blueprint handlers
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
QUART_ENV=development
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

- [Quart Documentation](https://quart.palletsprojects.com/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [Quart WebSockets](https://quart.palletsprojects.com/en/latest/how_to_guides/websockets.html)

