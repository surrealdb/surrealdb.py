"""Application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""

    SURREALDB_URL = os.getenv("SURREALDB_URL", "ws://localhost:8000/rpc")
    SURREALDB_NAMESPACE = os.getenv("SURREALDB_NAMESPACE", "test")
    SURREALDB_DATABASE = os.getenv("SURREALDB_DATABASE", "test")
    SURREALDB_USERNAME = os.getenv("SURREALDB_USERNAME", "root")
    SURREALDB_PASSWORD = os.getenv("SURREALDB_PASSWORD", "root")


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False


# Configuration dictionary
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
