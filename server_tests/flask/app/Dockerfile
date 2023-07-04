FROM rust:latest as builder

RUN apt-get update
RUN apt install python3.9 -y
RUN apt-get install -y python3-dev -y
RUN apt-get install -y python3-pip -y
RUN pip install --upgrade pip setuptools wheel

RUN apt-get install libclang-dev -y

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD . /app

RUN pip install ./surreal.py/

# server build
FROM python:3.9

RUN apt-get update \
    && apt-get install -y python3-dev python3-pip \
    && pip install --upgrade pip setuptools wheel \
    && pip install flask gunicorn

WORKDIR /app

# copy the built python packages from the previous stage to the new image
COPY --from=builder /usr/local/lib/python3.9/dist-packages /usr/local/lib/python3.9/site-packages

# copy the python server app code to the new image
COPY --from=builder /app /app

# Run the python server using gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "--timeout", "900", "--preload", "main:app"]
