from surrealdb import SurrealDB


def main():
    db = SurrealDB("ws://localhost:8000")
    db.connect()
    db.use("example_ns", "example_db")
    db.sign_in("root", "root")

    # Insert a record
    new_user = {"name": "Alice", "age": 30}
    inserted_record = db.insert("users", new_user)
    print(f"Inserted Record: {inserted_record}")

    # Retrieve the record
    retrieved_users = db.select("users")
    print(f"Retrieved Users: {retrieved_users}")

    db.close()


if __name__ == '__main__':
    main()
