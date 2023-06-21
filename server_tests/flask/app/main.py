from flask import Flask
from surrealdb import SurrealDB

app = Flask(__name__)


def create_connection():
    one = SurrealDB("ws://surrealdb:8000")
    two = SurrealDB("http://surrealdb:8000")

@app.route('/')
def hello():
    create_connection()
    return 'Hello, World!'


if __name__ == '__main__':
    app.run(port=5002)
