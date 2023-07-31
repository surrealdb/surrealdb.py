from flask import Flask
from surrealdb import SurrealDB


app = Flask(__name__)


LOCATION = "0.0.0.0"


def create_connection():
    _ = SurrealDB(f"ws://{LOCATION}:8000/namespace/database")
    _ = SurrealDB(f"http://{LOCATION}:8000/namespace/database")


@app.route('/')
def hello():
    create_connection()
    return 'Hello, World!'


@app.route('/ws')
def ws():
    connection = SurrealDB(f"ws://{LOCATION}:8000/ws_namespace/ws_database")
    connection.signin({
        "username": "root",
        "password": "root",
    })
    connection.query("CREATE user:ws_one SET name = 'ws_one';")
    connection.query("CREATE user:ws_two SET name = 'ws_two';")
    outcome = connection.query("SELECT * FROM user;")
    return outcome


@app.route('/ws/two')
def ws_two():
    connection = SurrealDB(f"ws://{LOCATION}:8000/ws_namespace/ws_database")
    connection.signin({
        "username": "root",
        "password": "root",
    })
    connection.query("CREATE user:ws_three SET name = 'ws_three';")
    connection.query("CREATE user:ws_four SET name = 'ws_four';")
    outcome = connection.query("SELECT * FROM user;")
    return outcome


@app.route('/http')
def http():
    connection = SurrealDB(f"http://{LOCATION}:8000/http_namespace/http_database")
    connection.signin({
        "username": "root",
        "password": "root",
    })
    connection.query("CREATE user:http_one SET name = 'http_one';")
    connection.query("CREATE user:http_two SET name = 'http_two';")
    outcome = connection.query("SELECT * FROM user;")
    return outcome


@app.route('/http/two')
def http_two():
    connection = SurrealDB(f"http://{LOCATION}:8000/http_namespace/http_database")
    connection.signin({
        "username": "root",
        "password": "root",
    })
    connection.query("CREATE user:http_three SET name = 'http_three';")
    connection.query("CREATE user:http_four SET name = 'http_four';")
    outcome = connection.query("SELECT * FROM user;")
    return outcome


if __name__ == '__main__':
    app.run(port=5002, host='0.0.0.0')

