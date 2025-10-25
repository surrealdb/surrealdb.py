# Django + SurrealDB Example

A comprehensive Django REST Framework example demonstrating SurrealDB integration with proper Django patterns, middleware, and ViewSets.

## Features

- **Django REST Framework**: Full API with ViewSets
- **Custom Middleware**: SurrealDB connection per request
- **Authentication**: Signup, signin endpoints
- **Serializers**: Data validation with DRF
- **Async Views**: Django 4.1+ async support
- **Management Commands**: DB utility commands
- **CORS**: Configured for frontend integration

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

# Run migrations (Django setup)
uv run python manage.py migrate
```

### Option 2: Using pip (Universal)

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Start SurrealDB
docker compose up -d

# Run migrations
python manage.py migrate
```

## Running the Application

### With uv (Recommended)

```bash
# Development server
uv run python manage.py runserver

# Or with auto-reload
uv run python manage.py runserver 0.0.0.0:8000
```

### With pip

```bash
# Development server
python manage.py runserver

# Or specify host/port
python manage.py runserver 0.0.0.0:8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Users

- `GET /api/users/` - List all users
- `POST /api/users/` - Create a new user
- `GET /api/users/{id}/` - Get user by ID
- `PUT /api/users/{id}/` - Update user
- `DELETE /api/users/{id}/` - Delete user

### Authentication

- `POST /api/auth/signup/` - User registration
- `POST /api/auth/signin/` - User login
- `POST /api/auth/logout/` - Logout

### Health Check

- `GET /health/` - Application health status

## Usage Examples

### Create a User

```bash
curl -X POST "http://localhost:8000/api/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
  }'
```

### List Users

```bash
curl "http://localhost:8000/api/users/"
```

### Update User

```bash
curl -X PUT "http://localhost:8000/api/users/users:johndoe/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Updated",
    "age": 31
  }'
```

## Project Structure

```
django/
├── manage.py                      # Django CLI
├── surrealdb_example/             # Project directory
│   ├── settings.py                # Django settings
│   ├── urls.py                    # URL routing
│   ├── asgi.py                    # ASGI config
│   └── wsgi.py                    # WSGI config
├── api/                           # Django app
│   ├── apps.py                    # App config
│   ├── views.py                   # API views/ViewSets
│   ├── serializers.py             # DRF serializers
│   ├── urls.py                    # App URLs
│   └── middleware.py              # Custom middleware
├── database.py                    # SurrealDB connection
├── config.py                      # Configuration
├── pyproject.toml                 # Modern dependencies (uv)
├── requirements.txt               # Universal dependencies (pip)
├── .env.example                   # Environment template
├── docker-compose.yml             # SurrealDB setup
└── README.md                      # This file
```

## Django-Specific Patterns

### Middleware

The example includes custom middleware for SurrealDB connection management:

```python
class SurrealDBMiddleware:
    """Manages SurrealDB connection per request."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    async def __call__(self, request):
        request.db = await get_connection()
        response = await self.get_response(request)
        await close_connection(request.db)
        return response
```

### ViewSets

Uses Django REST Framework ViewSets for clean API design:

```python
class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    
    def get_queryset(self):
        # Fetch from SurrealDB
        return self.request.db.select("users")
```

### Serializers

DRF serializers for validation:

```python
class UserSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    age = serializers.IntegerField(required=False)
```

## Configuration

Environment variables (`.env`):

```
SURREALDB_URL=ws://localhost:8000/rpc
SURREALDB_NAMESPACE=test
SURREALDB_DATABASE=test
SURREALDB_USERNAME=root
SURREALDB_PASSWORD=root

DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

## Management Commands

Custom Django management commands for database operations:

```bash
# Clear all data
python manage.py clear_db

# Load sample data
python manage.py load_sample_data
```

## Development

### Running Tests

```bash
# With uv
uv run python manage.py test

# With pip
python manage.py test
```

### Code Formatting

```bash
# Format code
ruff format .

# Lint
ruff check .
```

## Django Admin

While SurrealDB doesn't use Django's ORM, you can still use the Django admin for other purposes. The example shows how to integrate both.

## Production Deployment

For production, use a proper WSGI/ASGI server:

```bash
# With Gunicorn (sync)
gunicorn surrealdb_example.wsgi:application

# With Uvicorn (async)
uvicorn surrealdb_example.asgi:application --workers 4
```

## Learn More

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [Django Async Views](https://docs.djangoproject.com/en/stable/topics/async/)

