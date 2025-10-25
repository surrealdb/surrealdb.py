# GraphQL + SurrealDB Example (Strawberry)

A comprehensive GraphQL server example demonstrating SurrealDB integration with Strawberry GraphQL, featuring queries, mutations, subscriptions, and DataLoader optimization.

## Features

- **Modern GraphQL**: Strawberry GraphQL with Python type hints
- **Full CRUD**: Complete user management via GraphQL
- **Queries**: Fetch data with flexible filtering
- **Mutations**: Create, update, and delete operations
- **Subscriptions**: Real-time updates via WebSocket
- **DataLoader**: Optimized N+1 query prevention
- **Authentication**: Signup, signin, and token management
- **Type Safety**: Full Python type hints throughout
- **GraphiQL**: Interactive API playground

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

The GraphQL API will be available at `http://localhost:8000/graphql`

## GraphQL Playground

Once running, visit:
- **GraphiQL**: http://localhost:8000/graphql
- Interactive playground for exploring the API

## GraphQL Schema

### Types

```graphql
type User {
  id: ID!
  name: String!
  email: String!
  age: Int
}

type AuthResponse {
  token: String!
  message: String!
}
```

### Queries

```graphql
type Query {
  # Get all users
  users: [User!]!
  
  # Get a single user by ID
  user(id: ID!): User
}
```

### Mutations

```graphql
type Mutation {
  # Create a new user
  createUser(name: String!, email: String!, age: Int): User!
  
  # Update an existing user
  updateUser(id: ID!, name: String, email: String, age: Int): User!
  
  # Delete a user
  deleteUser(id: ID!): Boolean!
  
  # User registration
  signup(
    namespace: String!
    database: String!
    access: String!
    email: String!
    password: String!
  ): AuthResponse!
  
  # User login
  signin(username: String!, password: String!): AuthResponse!
}
```

### Subscriptions

```graphql
type Subscription {
  # Subscribe to user updates
  userUpdated: User!
}
```

## Usage Examples

### Query: Get All Users

```graphql
query GetAllUsers {
  users {
    id
    name
    email
    age
  }
}
```

### Query: Get Single User

```graphql
query GetUser {
  user(id: "users:john") {
    id
    name
    email
  }
}
```

### Mutation: Create User

```graphql
mutation CreateUser {
  createUser(
    name: "John Doe"
    email: "john@example.com"
    age: 30
  ) {
    id
    name
    email
    age
  }
}
```

### Mutation: Update User

```graphql
mutation UpdateUser {
  updateUser(
    id: "users:john"
    name: "John Updated"
    age: 31
  ) {
    id
    name
    age
  }
}
```

### Mutation: Delete User

```graphql
mutation DeleteUser {
  deleteUser(id: "users:john")
}
```

### Mutation: Signup

```graphql
mutation Signup {
  signup(
    namespace: "test"
    database: "test"
    access: "user"
    email: "user@example.com"
    password: "secure_password"
  ) {
    token
    message
  }
}
```

### Subscription: User Updates

```graphql
subscription UserUpdates {
  userUpdated {
    id
    name
    email
    age
  }
}
```

## Using with cURL

### Query

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ users { id name email } }"
  }'
```

### Mutation

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createUser(name: \"Jane\", email: \"jane@example.com\") { id name } }"
  }'
```

## Project Structure

```
graphql/
├── main.py                     # Application entry point
├── config.py                   # Configuration management
├── database.py                 # Database connection
├── dataloaders.py              # DataLoader for optimization
├── schema/                     # GraphQL schema
│   ├── __init__.py
│   ├── types.py                # GraphQL type definitions
│   ├── queries.py              # Query resolvers
│   ├── mutations.py            # Mutation resolvers
│   └── subscriptions.py        # Subscription resolvers
├── pyproject.toml              # Modern dependencies (uv)
├── requirements.txt            # Universal dependencies (pip)
├── .env.example                # Environment template
├── docker-compose.yml          # SurrealDB setup
└── README.md                   # This file
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

## Features in Detail

### DataLoader

The example includes DataLoader implementation for batching and caching database queries, preventing N+1 query problems:

```python
# Efficiently loads multiple users in a single query
user_loader = UserDataLoader(db)
users = await asyncio.gather(*[user_loader.load(id) for id in user_ids])
```

### Subscriptions

Real-time updates via WebSocket using SurrealDB live queries:

```python
# Subscribe to user changes
async for user in subscribe_to_users():
    yield user  # Pushed to client in real-time
```

### Type Safety

Full type hints with Strawberry's type system:

```python
@strawberry.type
class User:
    id: str
    name: str
    email: str
    age: Optional[int] = None
```

## Development

### Running Tests

```bash
# With uv
uv run pytest

# With pip
pytest
```

### Code Formatting

```bash
# Format code
ruff format .

# Lint
ruff check .
```

## GraphQL Best Practices

This example demonstrates:
- ✅ **Type safety** with Strawberry types
- ✅ **Async resolvers** for better performance
- ✅ **DataLoader** for query optimization
- ✅ **Subscriptions** for real-time features
- ✅ **Error handling** with proper GraphQL errors
- ✅ **Authentication** patterns
- ✅ **Field resolvers** for computed fields

## Learn More

- [Strawberry GraphQL Documentation](https://strawberry.rocks/)
- [GraphQL Specification](https://graphql.org/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [DataLoader Pattern](https://github.com/graphql/dataloader)

