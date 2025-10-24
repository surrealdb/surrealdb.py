"""
Utils for handling processes around data
"""

from typing import Union

from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table


def process_record(record: RecordIdType) -> Union[RecordID, Table]:
    if isinstance(record, RecordID):
        return record
    elif isinstance(record, Table):
        return record
    else:
        if ":" in record:
            return RecordID.parse(record)
        else:
            return Table(record)
