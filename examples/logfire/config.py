"""Configuration management for the Logfire example."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    # SurrealDB settings
    surrealdb_url: str
    surrealdb_namespace: str
    surrealdb_database: str
    surrealdb_username: str
    surrealdb_password: str

    # Logfire settings
    logfire_token: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            surrealdb_url=os.getenv("SURREALDB_URL", "ws://localhost:8000/rpc"),
            surrealdb_namespace=os.getenv("SURREALDB_NAMESPACE", "test"),
            surrealdb_database=os.getenv("SURREALDB_DATABASE", "test"),
            surrealdb_username=os.getenv("SURREALDB_USERNAME", "root"),
            surrealdb_password=os.getenv("SURREALDB_PASSWORD", "root"),
            logfire_token=os.getenv("LOGFIRE_TOKEN"),
        )


# Global configuration instance
config = Config.from_env()
