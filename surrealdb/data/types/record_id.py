from dataclasses import dataclass


@dataclass
class RecordID:
    def __init__(self, table_name: str, identifier):
        self.table_name = table_name
        self.id = identifier

    def __str__(self) -> str:
        return f"{self.table_name}:{self.id}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(table_name={self.table_name}, record_id={self.id})".format(
            self=self
        )

    @staticmethod
    def parse(record_str: str):
        if ":" not in record_str:
            raise ValueError(
                'invalid string provided for parse. the expected string format is "table_name:record_id"'
            )

        table, record_id = record_str.split(":")
        return RecordID(table, record_id)
