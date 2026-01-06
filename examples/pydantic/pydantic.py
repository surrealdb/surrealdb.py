import json

from surrealdb import RecordID, Surreal

try:
    from pydantic import BaseModel
except ImportError:
    raise ImportError("Pydantic is not installed")


# BaseModel to show how serialization and deserialization work, between JSON,
# python dictionaries, and SurrealDB records
class Person(BaseModel):
    id: RecordID | None = None
    name: str

    def __str__(self):
        return f"Person(id={self.id}, name={self.name})"


def main():
    with Surreal("mem://") as db:
        db.use("test", "test")
        # Note: Embedded databases don't require authentication

        # Person from JSON
        person_json = json.dumps(
            {"id": "person:abc", "name": "Martin", "team": "team:xyz"}
        )
        person_loaded = Person.model_validate_json(person_json)
        print(f"Loaded person ({type(person_loaded)}): {person_loaded}")
        assert isinstance(person_loaded.id, RecordID)
        assert person_loaded.id.table_name == "person"
        assert person_loaded.id.id == "abc"

        # Insert in DB
        person_value = db.create("person", person_loaded.model_dump())
        print(f"Created person ({type(person_value)}): {person_value}")
        assert isinstance(person_value, dict)
        assert person_value["id"] == RecordID("person", "abc")

        # Deserialize the person
        person = Person.model_validate(person_value)
        print(f"Deserialized person ({type(person)}): {person}")
        assert person.id == RecordID("person", "abc")

        # Serialize to JSON
        person_json_2 = person.model_dump_json()
        print(f"Serialized person to JSON: {person_json_2}")

        # JSON schema
        print(f"JSON schema: {Person.model_json_schema()}")

        # List of people
        people_raw = db.select("person")
        if isinstance(people_raw, list):
            people = [Person.model_validate(person) for person in people_raw]
            print(f"List of people ({type(people)}): {people}")


if __name__ == "__main__":
    main()
