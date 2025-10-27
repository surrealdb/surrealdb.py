"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    surrealdb_url: str = "ws://localhost:8000/rpc"
    surrealdb_namespace: str = "test"
    surrealdb_database: str = "test"
    surrealdb_username: str = "root"
    surrealdb_password: str = "root"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
