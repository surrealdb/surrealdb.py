# FastMCP + SurrealDB Example

An MCP (Model Context Protocol) server example demonstrating SurrealDB integration, featuring database tools and resources for AI assistants like Claude.

## Features

- **MCP Server**: Compliant Model Context Protocol implementation
- **Database Tools**: CRUD operations exposed as MCP tools
- **Resources**: Database connection info as MCP resources
- **Async Operations**: Full async support
- **Type Safety**: Proper error handling and validation
- **AI-Ready**: Designed for use with Claude and other AI assistants

## Prerequisites

- Python 3.10+
- Docker (for running SurrealDB)
- Claude Desktop or other MCP client

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

## Running the Server

### With uv (Recommended)

```bash
# Run the MCP server
uv run python server.py
```

### With pip

```bash
# Run the MCP server
python server.py
```

### Standalone Mode (Either Method)

### With Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

**Using uv (Recommended):**
```json
{
  "mcpServers": {
    "surrealdb": {
      "command": "uv",
      "args": ["run", "python", "/path/to/examples/fastmcp/server.py"],
      "env": {
        "SURREALDB_URL": "ws://localhost:8000/rpc",
        "SURREALDB_NAMESPACE": "test",
        "SURREALDB_DATABASE": "test",
        "SURREALDB_USERNAME": "root",
        "SURREALDB_PASSWORD": "root"
      }
    }
  }
}
```

**Using pip:**
```json
{
  "mcpServers": {
    "surrealdb": {
      "command": "python",
      "args": ["/path/to/examples/fastmcp/server.py"],
      "env": {
        "SURREALDB_URL": "ws://localhost:8000/rpc",
        "SURREALDB_NAMESPACE": "test",
        "SURREALDB_DATABASE": "test",
        "SURREALDB_USERNAME": "root",
        "SURREALDB_PASSWORD": "root"
      }
    }
  }
}
```

## Available Tools

### User Management

- `create_user` - Create a new user
  - Parameters: name (string), email (string), age (optional int)
  
- `list_users` - List all users
  - No parameters
  
- `get_user` - Get user by ID
  - Parameters: user_id (string)
  
- `update_user` - Update user
  - Parameters: user_id (string), name (optional), email (optional), age (optional)
  
- `delete_user` - Delete user
  - Parameters: user_id (string)

### Query Execution

- `execute_query` - Execute a SurrealQL query
  - Parameters: query (string)

## Available Resources

- `surrealdb://config` - Database configuration information
- `surrealdb://schema` - Database schema (if available)

## Usage with Claude

Once configured, you can interact with Claude using natural language:

```
User: "Create a new user named John Doe with email john@example.com"
Claude: [Uses create_user tool]

User: "Show me all users"
Claude: [Uses list_users tool]

User: "Update user users:johndoe to change their age to 31"
Claude: [Uses update_user tool]

User: "Execute this query: SELECT * FROM users WHERE age > 25"
Claude: [Uses execute_query tool]
```

## Project Structure

```
fastmcp/
├── server.py            # MCP server implementation
├── config.py            # Configuration management
├── database.py          # Database connection
├── tools.py             # MCP tool definitions
├── resources.py         # MCP resource handlers
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

### Testing the Server

```bash
# Test with MCP inspector
npx @modelcontextprotocol/inspector python server.py
```

### Code Formatting

```bash
# Format code
ruff format .

# Lint
ruff check .
```

## Learn More

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)
- [Claude Desktop](https://claude.ai/desktop)

## Security Notes

- Always use environment variables for credentials
- Never expose root credentials in production
- Implement proper authentication/authorization
- Validate all input parameters
- Use prepared queries when possible

