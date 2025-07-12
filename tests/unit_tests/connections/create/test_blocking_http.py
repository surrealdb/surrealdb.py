from unittest import TestCase, main

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


class TestHttpSurrealConnection(TestCase):
    def setUp(self):
        self.url = "http://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.data = {
            "name": self.username,
            "password": self.password,
        }
        self.connection = BlockingHttpSurrealConnection(self.url)
        self.connection.signin(self.vars_params)
        self.connection.use(namespace=self.namespace, database=self.database_name)
        self.connection.query("DELETE person;")

    def test_create_string(self):
        outcome = self.connection.create("person")
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(len(self.connection.query("SELECT * FROM person;")), 1)
        self.connection.query("DELETE person;")

    def test_create_string_with_data(self):
        outcome = self.connection.create("person", self.data)
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(self.password, outcome["password"])
        self.assertEqual(self.username, outcome["name"])

        outcome = self.connection.query("SELECT * FROM person;")
        self.assertEqual(len(outcome), 1)
        self.assertEqual("person", outcome[0]["id"].table_name)
        self.assertEqual(self.password, outcome[0]["password"])
        self.assertEqual(self.username, outcome[0]["name"])

        self.connection.query("DELETE person;")

    def test_create_string_with_data_and_id(self):
        first_outcome = self.connection.create("person:tobie", self.data)
        self.assertEqual("person", first_outcome["id"].table_name)
        self.assertEqual("tobie", first_outcome["id"].id)
        self.assertEqual(self.password, first_outcome["password"])
        self.assertEqual(self.username, first_outcome["name"])

        outcome = self.connection.query("SELECT * FROM person;")
        self.assertEqual(len(outcome), 1)
        self.assertEqual("person", outcome[0]["id"].table_name)
        self.assertEqual("tobie", outcome[0]["id"].id)
        self.assertEqual(self.password, outcome[0]["password"])
        self.assertEqual(self.username, outcome[0]["name"])

        self.connection.query("DELETE person;")

    def test_create_record_id(self):
        record_id = RecordID("person", 1)
        outcome = self.connection.create(record_id)
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(1, outcome["id"].id)

        self.assertEqual(len(self.connection.query("SELECT * FROM person;")), 1)

        self.connection.query("DELETE person;")

    def test_create_record_id_with_data(self):
        record_id = RecordID("person", 1)
        outcome = self.connection.create(record_id, self.data)
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(1, outcome["id"].id)
        self.assertEqual(self.password, outcome["password"])
        self.assertEqual(self.username, outcome["name"])

        outcome = self.connection.query("SELECT * FROM person;")
        self.assertEqual(len(outcome), 1)
        self.assertEqual("person", outcome[0]["id"].table_name)
        self.assertEqual(self.password, outcome[0]["password"])
        self.assertEqual(self.username, outcome[0]["name"])

        self.connection.query("DELETE person;")

    def test_create_table(self):
        table = Table("person")
        outcome = self.connection.create(table)
        self.assertEqual("person", outcome["id"].table_name)

        self.assertEqual(len(self.connection.query("SELECT * FROM person;")), 1)

        self.connection.query("DELETE person;")

    def test_create_table_with_data(self):
        table = Table("person")
        outcome = self.connection.create(table, self.data)
        self.assertEqual("person", outcome["id"].table_name)
        self.assertEqual(self.password, outcome["password"])
        self.assertEqual(self.username, outcome["name"])

        outcome = self.connection.query("SELECT * FROM person;")
        self.assertEqual(len(outcome), 1)
        self.assertEqual("person", outcome[0]["id"].table_name)
        self.assertEqual(self.password, outcome[0]["password"])
        self.assertEqual(self.username, outcome[0]["name"])

        self.connection.query("DELETE person;")


if __name__ == "__main__":
    main()
