FROM ghcr.io/astral-sh/uv:latest

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app

# Set working directory and switch to app user
WORKDIR /app
USER app

# Copy dependency files first for better caching
COPY --chown=app:app pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy source code
COPY --chown=app:app src/ ./src/
COPY --chown=app:app tests/ ./tests/
COPY --chown=app:app README.md LICENSE ./

# Build and install the package
RUN uv build && uv pip install dist/*.whl

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD uv run python -c "import surrealdb; print('SurrealDB Python client is ready')" || exit 1

# Default command - can be overridden
CMD ["uv", "run", "python", "-c", "import surrealdb; print('SurrealDB Python client container is running')"]

