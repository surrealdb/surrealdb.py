FROM centos:latest

# Set the working directory
WORKDIR /app

# Copy the source code
COPY src /app/src

# Copy the .cargo directory
COPY .cargo /app/.cargo

# Copy the surrealdb directory
COPY surrealdb /app/surrealdb

# Copy the Cargo.toml file
COPY Cargo.toml /app/Cargo.toml

# Copy the pyproject.toml file
COPY pyproject.toml /app/pyproject.toml

# Copy the setup.py file
COPY setup.py /app/setup.py

EXPOSE 18000

CMD ["bash", "-c", "trap : TERM INT; sleep infinity & wait"]

