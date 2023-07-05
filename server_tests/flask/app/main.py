from flask import Flask
from surrealdb import SurrealDB


app = Flask(__name__)

with app.app_context():
    global ROCKS_CONNECTION
    global MEMORY_CONNECTION
    ROCKS_CONNECTION = SurrealDB("rocksdb:///tmp/test.db")
    ROCKS_CONNECTION.use_namespace("rocks_namespace")
    ROCKS_CONNECTION.use_database("rocks_database")

    MEMORY_CONNECTION = SurrealDB("memory")
    MEMORY_CONNECTION.use_namespace("mem_namespace")
    MEMORY_CONNECTION.use_database("mem_database")


def create_connection():
    _ = SurrealDB("ws://surrealdb:8000/namespace/database")
    _ = SurrealDB("http://surrealdb:8000/namespace/database")


@app.route('/')
def hello():
    create_connection()
    return 'Hello, World!'


@app.route('/ws')
def ws():
    connection = SurrealDB("ws://surrealdb:8000/ws_namespace/ws_database")
    connection.signin({
        "username": "root",
        "password": "root",
    })
    connection.query("CREATE user:ws_one SET name = 'ws_one';")
    connection.query("CREATE user:ws_two SET name = 'ws_two';")
    outcome = connection.query("SELECT * FROM user;")
    return outcome


@app.route('/http')
def http():
    connection = SurrealDB("http://surrealdb:8000/http_namespace/http_database")
    connection.signin({
        "username": "root",
        "password": "root",
    })
    connection.query("CREATE user:http_one SET name = 'http_one';")
    connection.query("CREATE user:http_two SET name = 'http_two';")
    outcome = connection.query("SELECT * FROM user;")
    return outcome


@app.route('/rocksdb')
def rocksdb():
    ROCKS_CONNECTION.signin({
        "username": "root",
        "password": "root",
    })
    ROCKS_CONNECTION.query("CREATE user:rocks_one SET name = 'rocks_one';")
    ROCKS_CONNECTION.query("CREATE user:rocks_two SET name = 'rocks_two';")
    outcome = ROCKS_CONNECTION.query("SELECT * FROM user;")
    return outcome


@app.route('/memory')
def memory():
    MEMORY_CONNECTION.query("CREATE user:memory_one SET name = 'memory_one';")
    MEMORY_CONNECTION.query("CREATE user:memory_two SET name = 'memory_two';")
    outcome = MEMORY_CONNECTION.query("SELECT * FROM user;")
    return outcome


if __name__ == '__main__':
    app.run(port=5002, host='0.0.0.0')
