FROM rust:latest

RUN apt-get update
RUN apt install python3.9 -y
RUN apt-get install -y python3-dev -y
RUN apt-get install -y python3-pip -y
RUN pip install --upgrade pip setuptools wheel
RUN pip install flask
RUN pip install gunicorn


# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD . /app


#RUN cd surreal.py && cargo clean
#RUN cd surreal.py && cargo update

RUN pip install ./surreal.py/

CMD ["gunicorn", "-w 4", "-b", "0.0.0.0:5002", "--timeout", "900", "main:app"]
