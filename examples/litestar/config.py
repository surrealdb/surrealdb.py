"""Application configuration."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Application settings."""

    surrealdb_url: str = os.getenv("SURREALDB_URL", "ws://localhost:8000/rpc")
    surrealdb_namespace: str = os.getenv("SURREALDB_NAMESPACE", "test")
    surrealdb_database: str = os.getenv("SURREALDB_DATABASE", "test")
    surrealdb_username: str = os.getenv("SURREALDB_USERNAME", "root")
    surrealdb_password: str = os.getenv("SURREALDB_PASSWORD", "root")


settings = Settings()
