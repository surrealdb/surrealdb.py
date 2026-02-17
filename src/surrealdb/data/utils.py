"""
Utils for handling processes around data
"""

from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table


def process_record(record: RecordIdType) -> RecordID | Table:
    if isinstance(record, RecordID) or isinstance(record, Table):
        return record
    else:
        if ":" in record:
            return RecordID.parse(record)
        else:
            return Table(record)
