class Table:
    def __init__(self, table_name: str):
        self.table_name = table_name

    def __str__(self) -> str:
        return f"{self.table_name}"

    def __repr__(self) -> str:
        return f"{self.table_name}"
