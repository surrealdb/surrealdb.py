from flask import Flask
from surrealdb import SurrealDB


app = Flask(__name__)


# ROCKS_CONNECTION = None

with app.app_context():
    global ROCKS_CONNECTION
    ROCKS_CONNECTION = SurrealDB("rocksdb:///tmp/test.db/namespace/database")


def create_connection():
    _ = SurrealDB("ws://surrealdb:8000/namespace/database")
    _ = SurrealDB("http://surrealdb:8000/namespace/database")


@app.route('/')
def hello():
    create_connection()
    return 'Hello, World!'


@app.route('/sql')
def sql():
    connection = SurrealDB("ws://surrealdb:8000/namespace/database")
    connection.signin({
        "username": "root",
        "password": "root",
    })
    connection.query("CREATE user:tobie SET name = 'Tobie';")
    connection.query("CREATE user:jaime SET name = 'Jaime';")
    outcome = connection.query("SELECT * FROM user;")
    return outcome


@app.route('/rocksdb')
def rocksdb():
    ROCKS_CONNECTION.signin({
        "username": "root",
        "password": "root",
    })
    ROCKS_CONNECTION.query("CREATE user:tobie SET name = 'Tobie';")
    ROCKS_CONNECTION.query("CREATE user:jaime SET name = 'Jaime';")
    outcome = ROCKS_CONNECTION.query("SELECT * FROM user;")
    return outcome


if __name__ == '__main__':
    app.run(port=5002, host='0.0.0.0')
