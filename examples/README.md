## Getting started
To get started install an instance of SurrealDB
Installation instructions are available at https://surrealdb.com/

## Usage (http)
All the functions are async therefore they have to be wrapped by an async function to work

### Creating a client 
Start off by creating a client
```python
client = HTTPClient("http://localhost:8000", namespace="test", database="test", username="root",password="root")\
```

### Create a record
#### Auto generated id
To create a record that automatically generates the id for you we can use the create_all() function  
```Returns: List of created objects```
```python
async def create_all():
    table = "hospital"
    data = {"name:": "A Hospital", "location":"earth"}
    response = await client.create_all(table, data)
    print(response)
```

#### Specify Your own id
To specify your id use the create_one() function  
```Returns: Created objects```  
```python
async def create_with_id():
    table = "hospital"
    custom_id = "customidhere"  # this is id but its reserved
    data = {"name": "A second Hospital", "location":"earth"}
    response = await client.create_one(table, custom_id, data)
    print(response)
```

### Reading data from the table
#### Reading all Data
To get all the data use the select_all() function  
```Returns: List of existing objects```  
```python
async def select_all():
    table = "hospital"
    response = await client.select_all(table)
    print(response)
```

#### Reading a single record
Surrealdb Stores data in each table with a unique record id, we can take advantage of that by 
using the select_one() function  
Note this name is going to be changed in the future  
```Returns: Object that was queried```  
```python
async def select_one():
    table = "hospital"
    custom_id = "customidhere"
    response = await client.select_one(table, custom_id)
    print(response)
```

### Updating a record
There are 2 methods for updating data learn the difference [here](https://stackoverflow.com/questions/28459418/use-of-put-vs-patch-methods-in-rest-api-real-life-scenarios)

#### Replacing the entire Record (PUT)
To replace the entire record use the replace_one() function
```Returns: Modified objects```
```python
async def replace_one():
    table = "hospital"
    custom_id = "customidhere"
    new_data = {"name": "A Replacement Hospital","location":"not earth"}
    response = await client.replace_one(table,custom_id,new_data)
    print(response)
```

#### Patching the record (PATCH)
It is possible to midify the record using the upsert_one() function  
The upsert_one() function can take a partial data and/or data that does not exist yet as parameters  
```Returns: Modified objects```
```python
async def upsert_one():
    table = "hospital"
    custom_id = "customidhere"
    partial_new_data = {"location":"on the sun", "fieldthatdint":"exist"}
    response = await client.upsert_one(table,custom_id,partial_new_data)
    print(response)
```

### Deleting Data
#### Delete all the data on a table
```Returns: None```
```python
async def delete_all():
    table = "hospital"
    await client.delete_all(table)
```

#### Delete Single record using id
```Returns: None```
```python
async def delete_one():
    table = "hospital"
    custom_id = "customidhere"
    await client.delete_one(table,custom_id)
```
### Custom Queries
SurrealDB has a very powerful query language with is similar to SQL. To take advantage of this powerful query language
we can use the execute() function
```Returns: List[Dict[str, Any]]```
```python
async def my_query():
    query = "SELECT * FROM hospital"
    data = await client.execute(query)
    print(data)
```
