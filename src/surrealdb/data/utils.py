"""
Utils for handling processes around data
"""

from typing import Union

from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


def process_thing(thing: Union[str, RecordID, Table]) -> Union[RecordID, Table]:
    if isinstance(thing, RecordID):
        return thing
    elif isinstance(thing, Table):
        return thing
    elif isinstance(thing, str):
        if ":" in thing:
            return RecordID.parse(thing)
        else:
            return Table(thing)
