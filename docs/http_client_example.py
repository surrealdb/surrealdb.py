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


# hospital:mpiw9ru2v6kkl2sto412
# hospital:c1xjgtof77x3a6creqg1

async def create_one():
    table = "hospital"
    eye_dee = "mpiw9ru2v6kkl2sto413"  # this is id but its reserved
    data = {"name": "A second Hospital"}
    response = await client.create_one(table, eye_dee, data)
    print(response)


async def select_all():
    table = "hospital"
    response = await client.select_all(table)
    print(response)


async def select_one():
    table = "hospital"
    eye_dee = "mpiw9ru2v6kkl2sto413"
    response = await client.select_one(table, eye_dee)
    print(response)


# this is an example to run your own queries
async def my_query():
    query = "INFO FOR DB;"
    data = await client.execute(query)
    print(data)


asyncio.run(create_one())
