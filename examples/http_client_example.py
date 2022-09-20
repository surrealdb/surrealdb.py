"""
Copyright © SurrealDB Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import asyncio

from surrealdb.clients.http import HTTPClient

# import the http client

# create a new client to connect to SurrealDB
client = HTTPClient(
    "http://localhost:8000",
    namespace="test",
    database="test",
    username="root",
    password="root",
)


async def create_all():
    """Use the client to create example data in a table."""
    table = "hospital"
    data = {"name:": "A Hospital", "location": "earth"}
    response = await client.create_all(table, data)
    print(response)


async def create_with_id():
    """
    Create a record with a specified id.

    This will raise an exception if the record already exists.
    """
    table = "hospital"
    custom_id = "customidhere"  # this is id but its reserved
    data = {"name": "A second Hospital", "location": "earth"}
    response = await client.create_one(table, custom_id, data)
    print(response)


async def select_all():
    """Query a table for all records."""
    table = "hospital"
    response = await client.select_all(table)
    print(response)


async def select_one():
    """Query a table for a specific record by the record's id."""
    table = "hospital"
    custom_id = "customidhere"
    response = await client.select_one(table, custom_id)
    print(response)


async def replace_one():
    """Replace a record with a specified id."""
    table = "hospital"
    custom_id = "customidhere"
    new_data = {"name": "A Replacement Hospital", "location": "not earth"}
    response = await client.replace_one(table, custom_id, new_data)
    print(response)


async def upsert_one():
    """Patch a record with a specified id."""
    table = "hospital"
    custom_id = "customidhere"
    partial_new_data = {"location": "on the sun", "fieldthatdidnt": "exist"}
    response = await client.upsert_one(table, custom_id, partial_new_data)
    print(response)


async def delete_all():
    """Delete all records in a table."""
    table = "hospital"
    await client.delete_all(table)


async def delete_one():
    """Delete a record with a specified id."""
    table = "hospital"
    custom_id = "customidhere"
    await client.delete_one(table, custom_id)


async def my_query():
    """Execute a custom query."""
    query = "SELECT * FROM hospital"
    data = await client.execute(query)
    print(data)


async def run_all():
    """Run all of the examples."""
    await create_all()
    await create_with_id()
    await select_all()
    await select_one()
    await replace_one()
    await upsert_one()
    await delete_one()
    await delete_all()
    await my_query()


asyncio.run(run_all())
