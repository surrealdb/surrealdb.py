from surrealdb import SurrealDB


def main():
    with SurrealDB(url="ws://localhost:8000") as db:
        db.sign_in("root", "root")
        db.use("test", "test")

        query = "SELECT * FROM users WHERE age > min_age;"
        variables = {"min_age": 25}

        results = db.query(query, variables)
        print(f"Query Results: {results}")


if __name__ == '__main__':
    main()
