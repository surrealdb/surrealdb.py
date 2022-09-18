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
# import the http client this client is not as feature rich as the websocket client coming soon
from surrealdb.clients.http import SurrealDBHTTPClient

# create a new client to connect to SurrealDB
client = SurrealDBHTTPClient("http://localhost:8000", namespace="test", database="test", username="root",
                             password="root")


# this is an example of using the client to create data in a table
async def create_all():
    table = "hospital"
    data = {"name:": "A Hospital"}
    response = await client.create_all(table, data)
    print(response)


# This will allow us to create a record and allow us to use our own ids
# if we run this twice it will raise record already exist
async def create_with_id():
    table = "hospital"
    eye_dee = "customidhere"  # this is id but its reserved
    data = {"name": "A second Hospital"}
    response = await client.create_one(table, eye_dee, data)
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
    eye_dee = "customidhere"
    response = await client.select_one(table, eye_dee)
    print(response)


# this is an example to run your own queries
async def my_query():
    query = "SELECT * FROM hospital"
    data = await client.execute(query)
    print(data)

# uncomment these one by one to run them, or you can uncomment them all at once
# asyncio.run(create_all())
# asyncio.run(create_with_id())
# asyncio.run(select_all())
# asyncio.run(select_one())
# asyncio.run(my_query())
