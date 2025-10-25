# Flask + SurrealDB Example

A comprehensive example demonstrating SurrealDB integration with Flask, featuring CRUD operations, authentication, and the application factory pattern with blueprints.

## Features

- **CRUD Operations**: Complete user management API
- **Authentication**: Signup, signin, and session invalidation
- **Application Factory**: Clean, scalable app structure
- **Blueprints**: Organized route handlers
- **Context Management**: Proper database connection lifecycle
- **Error Handling**: Comprehensive exception handling
- **CORS Support**: Ready for frontend integration

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
# Development mode
uv run flask run --debug

# Production mode with Gunicorn
uv run gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

### With pip

```bash
# Development mode
flask run --debug

# Production mode with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
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

### Update a User

```bash
curl -X PUT "http://localhost:5000/api/users/users:johndoe" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Updated",
    "email": "john.updated@example.com"
  }'
```

### Delete a User

```bash
curl -X DELETE "http://localhost:5000/api/users/users:johndoe"
```

### Sign Up

```bash
curl -X POST "http://localhost:5000/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "test",
    "database": "test",
    "access": "user",
    "email": "user@example.com",
    "password": "secure_password"
  }'
```

## Project Structure

```
flask/
├── app.py               # Application factory
├── config.py            # Configuration management
├── database.py          # Database connection
├── routes/              # Blueprint handlers
│   ├── __init__.py
│   ├── users.py         # User CRUD endpoints
│   └── auth.py          # Authentication endpoints
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
FLASK_ENV=development
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

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [Flask Blueprints](https://flask.palletsprojects.com/en/latest/blueprints/)

