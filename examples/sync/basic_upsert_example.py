from surrealdb.surrealdb import SurrealDB

with SurrealDB("ws://localhost:8000") as db:
    db.sign_in("root", "root")
    db.use("example_ns", "example_db")

    upsert_data = {"name": "Charlie", "age": 35}
    result = db.upsert("users", upsert_data)
    print(f"Upsert Result: {result}")
