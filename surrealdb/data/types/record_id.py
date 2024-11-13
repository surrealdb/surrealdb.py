
class RecordID:
    def __init__(self, table_name: str, identifier):
        self.table_name = table_name
        self.id = identifier

    def __repr__(self) -> str:
        return f"{self.table_name}:{self.id}"


