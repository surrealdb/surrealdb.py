FROM ubuntu:latest

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

RUN apt update
RUN apt install -y clang
RUN apt-get install -y libclang-dev
RUN apt install -y python3
RUN apt install -y python3-pip
RUN apt install -y curl
RUN apt install -y vim
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
RUN export PATH="$HOME/.cargo/bin:$PATH"
RUN pip3 install setuptools_rust
RUN python3 setup.py bdist_wheel

# docker build . -t package-test
# docker run -d -p 18000:18000 package-test

EXPOSE 18000

CMD ["bash", "-c", "trap : TERM INT; sleep infinity & wait"]

