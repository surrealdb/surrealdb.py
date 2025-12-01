"""Utility functions for Jupyter notebooks."""

import json
from typing import Any, List

import pandas as pd
from surrealdb import AsyncSurreal


def pretty_print(data: Any) -> None:
    """Pretty print data in JSON format.

    Args:
        data: Data to print (dict, list, etc.)
    """
    print(json.dumps(data, indent=2, default=str))


def to_dataframe(data: List[dict]) -> pd.DataFrame:
    """Convert SurrealDB results to Pandas DataFrame.

    Args:
        data: List of records from SurrealDB

    Returns:
        Pandas DataFrame

    Example:
        ```python
        users = await db.select("users")
        df = to_dataframe(users)
        df.head()
        ```
    """
    if not data:
        return pd.DataFrame()

    # Convert RecordID objects to strings for DataFrame compatibility
    cleaned_data = []
    for record in data:
        cleaned_record = {}
        for key, value in record.items():
            if hasattr(value, "__str__") and not isinstance(
                value, (str, int, float, bool, type(None))
            ):
                cleaned_record[key] = str(value)
            else:
                cleaned_record[key] = value
        cleaned_data.append(cleaned_record)

    return pd.DataFrame(cleaned_data)


async def sample_data(db: AsyncSurreal) -> None:
    """Load sample data into the database.

    Args:
        db: Connected database instance
    """
    # Sample users
    users = [
        {"name": "Alice Johnson", "email": "alice@example.com", "age": 28, "city": "New York"},
        {"name": "Bob Smith", "email": "bob@example.com", "age": 35, "city": "San Francisco"},
        {"name": "Carol White", "email": "carol@example.com", "age": 42, "city": "Chicago"},
        {"name": "David Brown", "email": "david@example.com", "age": 31, "city": "Boston"},
        {"name": "Eve Davis", "email": "eve@example.com", "age": 26, "city": "Seattle"},
    ]

    for user in users:
        await db.create("users", user)

    print(f"✅ Loaded {len(users)} sample users")


async def clear_table(db: AsyncSurreal, table: str) -> None:
    """Clear all records from a table.

    Args:
        db: Connected database instance
        table: Table name to clear
    """
    await db.delete(table)
    print(f"✅ Cleared table: {table}")


def display_schema(data: List[dict]) -> None:
    """Display the schema of the data.

    Args:
        data: List of records
    """
    if not data:
        print("No data to analyze")
        return

    print("Schema Analysis:")
    print("=" * 50)

    # Get all unique keys
    all_keys = set()
    for record in data:
        all_keys.update(record.keys())

    # Analyze each field
    for key in sorted(all_keys):
        types = set()
        null_count = 0

        for record in data:
            if key in record:
                value = record[key]
                if value is None:
                    null_count += 1
                else:
                    types.add(type(value).__name__)

        type_str = ", ".join(sorted(types)) if types else "None"
        print(f"  {key}: {type_str} ({null_count}/{len(data)} null)")
