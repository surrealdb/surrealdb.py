from flask import Flask
from surrealdb import SurrealDB
from surrealdb.connection_interface import ConnectionController

app = Flask(__name__)


def create_connection():
    one = SurrealDB("ws://surrealdb:8000/database/namespace")
    two = SurrealDB("http://surrealdb:8000/database/namespace")


@app.route('/')
def hello():
    create_connection()
    return 'Hello, World!'


@app.route('/sql')
def sql():
    connection = SurrealDB("ws://surrealdb:8000/database/namespace")
    connection.signin({
        "username": "root",
        "password": "root",
    })
    connection.query("CREATE user:tobie SET name = 'Tobie';")
    connection.query("CREATE user:jaime SET name = 'Jaime';")
    outcome = connection.query("SELECT * FROM user;")
    return outcome


@app.route("/main/one")
def main_one():
    print(f"before: {ConnectionController.instances} {ConnectionController.main_connection}")
    main_connection = SurrealDB("ws://surrealdb:8000/database/namespace", main_connection=True)
    main_connection.signin({
        "username": "root",
        "password": "root",
    })
    print(f"after: {ConnectionController.instances} {ConnectionController.main_connection}")
    return main_connection.query("SELECT * FROM user;")


@app.route("/main/two")
def main_two():
    main_connection = SurrealDB(main_connection=True)
    return main_connection.query("SELECT * FROM user;")


if __name__ == '__main__':
    app.run(port=5002, host='0.0.0.0')
