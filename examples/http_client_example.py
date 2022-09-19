"""
Copyright © SurrealDB Ltd
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
# import the http client
from surrealdb.clients.http import HTTPClient

# create a new client to connect to SurrealDB
client = HTTPClient("http://localhost:8000", namespace="test", database="test", username="root",
                             password="root")


# this is an example of using the client to create data in a table
async def create_all():
    table = "hospital"
    data = {"name:": "A Hospital", "location": "earth"}
    response = await client.create_all(table, data)
    print(response)


# This will allow us to create a record and allow us to use our own ids
# if we run this twice it will raise record already exist
async def create_with_id():
    table = "hospital"
    custom_id = "customidhere"  # this is id but its reserved
    data = {"name": "A second Hospital", "location": "earth"}
    response = await client.create_one(table, custom_id, data)
    print(response)


# this queries the table for all the records that exist
# try adding more records with the above create functions to see it in action
async def select_all():
    table = "hospital"
    response = await client.select_all(table)
    print(response)


# this queries the table and the specific record id
async def select_one():
    table = "hospital"
    custom_id = "customidhere"
    response = await client.select_one(table, custom_id)
    print(response)


# This is an example to replace the data at the specified id
async def replace_one():
    table = "hospital"
    custom_id = "customidhere"
    new_data = {"name": "A Replacement Hospital", "location": "not earth"}
    response = await client.replace_one(table, custom_id, new_data)
    print(response)


# This is an example to patch the data at the specified id
async def upsert_one():
    table = "hospital"
    custom_id = "customidhere"
    partial_new_data = {"location": "on the sun", "fieldthatdidnt": "exist"}
    response = await client.upsert_one(table, custom_id, partial_new_data)
    print(response)


# This is an example to delete all the data
async def delete_all():
    table = "hospital"
    await client.delete_all(table)


# This is an example to delete only the specified
async def delete_one():
    table = "hospital"
    custom_id = "customidhere"
    await client.delete_one(table, custom_id)


# this is an example to run your own queries
async def my_query():
    query = "SELECT * FROM hospital"
    data = await client.execute(query)
    print(data)

async def run_all():
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

