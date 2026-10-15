"""
Utils for handling processes around data
"""

from surrealdb.data.types.record_id import RecordID, RecordIdType, StringRecordId
from surrealdb.data.types.table import Table


def process_record(record: RecordIdType) -> RecordID | StringRecordId | Table:
    if isinstance(record, (RecordID, StringRecordId, Table)):
        return record
    else:
        if ":" in record:
            return RecordID.parse(record)
        else:
            return Table(record)
