import os
from unittest import TestCase, main

from surrealdb.request_message.sql_adapter import SqlAdapter


class TestSqlAdapter(TestCase):
    def setUp(self):
        self.expected_sql = "CREATE user:tobie SET name = 'Tobie'; CREATE user:jaime SET name = 'Jaime';"

    def test_from_docstring(self):
        query = """
        CREATE user:tobie SET name = 'Tobie';
        CREATE user:jaime SET name = 'Jaime';
        """
        sql = SqlAdapter.from_docstring(query)
        self.assertEqual(self.expected_sql, sql)
        query = """


                CREATE user:tobie SET name = 'Tobie';

                CREATE 
                user:jaime 
                SET name = 'Jaime';


                """
        sql = SqlAdapter.from_docstring(query)
        self.assertEqual(self.expected_sql, sql)

    def test_from_list(self):
        query = [
            "CREATE user:tobie SET name = 'Tobie';",
            "",
            "CREATE user:jaime SET name = 'Jaime'",
        ]
        sql = SqlAdapter.from_list(query)
        self.assertEqual(self.expected_sql, sql)

    def test_from_file(self):
        current_file_path = os.path.abspath(__file__)

        # Get the directory of the current file
        directory = os.path.dirname(current_file_path)
        file_path = os.path.join(directory, "test.sql")
        sql = SqlAdapter.from_file(str(file_path))
        expected_sql = (
            ""
            "CREATE user:tobie SET name = 'Tobie'; "
            "CREATE user:jaime SET name = 'Jaime'; "
            "CREATE user:three SET name = 'Three';"
        )
        self.assertEqual(expected_sql, sql)


if __name__ == "__main__":
    main()
