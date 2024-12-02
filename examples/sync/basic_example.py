from surrealdb import SurrealDB


def main():
    with SurrealDB("ws://localhost:8000") as db:
        db.use("test", "test")
        token = db.sign_in("root", "root")

        print("Using methods")
        print(
            "create: ",
            db.create(
                "person",
                {
                    "user": "me",
                    "pass": "safe",
                    "marketing": True,
                    "tags": ["python", "documentation"],
                },
            ),
        )
        print("read: ", db.select("person"))
        print(
            "update: ",
            db.update(
                "person",
                {
                    "user": "you",
                    "pass": "very_safe",
                    "marketing": False,
                    "tags": ["Awesome"],
                },
            ),
        )
        print("delete: ", db.delete("person"))

        # You can also use the query method
        # doing all of the above and more in SurrealQl

        # In SurrealQL you can do a direct insert
        # and the table will be created if it doesn't exist
        print("Using just db.query")
        print(
            "create: ",
            db.query(
                """
        insert into person {
            user: 'me',
            pass: 'very_safe',
            tags: ['python', 'documentation']
        };
    
        """
            ),
        )
        print("read: ", db.query("select * from person"))

        print(
            "update: ",
            db.query(
                """
        update person content {
            user: 'you',
            pass: 'more_safe',
            tags: ['awesome']
        };
    
        """
            ),
        )
        print("delete: ", db.query("delete person"))


if __name__ == '__main__':
    main()
