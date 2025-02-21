from typing import Optional, List, Dict, Any, Union, Coroutine
from uuid import UUID
from asyncio import Queue
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


class AsyncTemplate:

    async def connect(self, url: str) -> Coroutine[Any, Any, None]:
        """Connects to a local or remote database endpoint.

        Args:
            url: The url of the database endpoint to connect to.
            options: An object with options to initiate the connection to SurrealDB.

        Example:
            # Connect to a remote endpoint
            await db.connect('https://cloud.surrealdb.com/rpc');
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def close(self) -> Coroutine[Any, Any, None]:
        """Closes the persistent connection to the database.

        Example:
            await db.close()
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def use(self, namespace: str, database: str) -> Coroutine[Any, Any, None]:
        """Switch to a specific namespace and database.

        Args:
            namespace: Switches to a specific namespace.
            database: Switches to a specific database.

        Example:
            await db.use('test', 'test')
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def authenticate(self, token: str) -> Coroutine[Any, Any, None]:
        """Authenticate the current connection with a JWT token.

        Args:
            token: The JWT authentication token.

        Example:
            await db.authenticate('insert token here')
        """
        raise NotImplementedError(f"authenticate not implemented for: {self}")

    async def invalidate(self) -> Coroutine[Any, Any, None]:
        """Invalidate the authentication for the current connection.

        Example:
            await db.invalidate()
        """
        raise NotImplementedError(f"invalidate not implemented for: {self}")

    async def signup(self, vars: Dict) -> Coroutine[Any, Any, str]:
        """Sign this connection up to a specific authentication scope.
        [See the docs](https://surrealdb.com/docs/sdk/python/methods/signup)

        Args:
            vars: Variables used in a signup query.

        Example:
            await db.signup({
                namespace: 'surrealdb',
                database: 'docs',
                access: 'user',

                # Also pass any properties required by the scope definition
                variables: {
                    email: 'info@surrealdb.com',
                    pass: '123456',
                },
            })
        """
        raise NotImplementedError(f"signup not implemented for: {self}")

    async def signin(self, vars: Dict) -> Coroutine[Any, Any, str]:
        """Sign this connection in to a specific authentication scope.
        [See the docs](https://surrealdb.com/docs/sdk/python/methods/signin)

        Args:
            vars: Variables used in a signin query.

        Example:
            await db.signin({
                username: 'root',
                password: 'surrealdb',
            })
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def let(self, key: str, value: Any) -> Coroutine[Any, Any, None]:
        """Assign a value as a variable for this connection.

        Args:
            key: Specifies the name of the variable.
            value: Assigns the value to the variable name.

        Example:
            # Assign the variable on the connection
            await db.let('name', {
                first: 'Tobie',
                last: 'Morgan Hitchcock',
            })

            # Use the variable in a subsequent query
            await db.query('CREATE person SET name = $name')
        """
        raise NotImplementedError(f"let not implemented for: {self}")

    async def unset(self, key: str) -> Coroutine[Any, Any, None]:
        """Removes a variable for this connection.

        Args:
            key: Specifies the name of the variable.

        Example:
            await db.unset('name')
        """
        raise NotImplementedError(f"let not implemented for: {self}")

    async def query(
        self, query: str, vars: Optional[Dict] = None
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """Run a unset of SurrealQL statements against the database.

        Args:
            query: Specifies the SurrealQL statements.
            vars: Assigns variables which can be used in the query.

        Example:
            await db.query(
                'CREATE person SET name = "John"; SELECT * FROM type::table($tb);',
                { tb: 'person' }
            )
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def select(
        self, thing: Union[str, RecordID, Table]
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """Select all records in a table (or other entity),
        or a specific record, in the database.

        This function will run the following query in the database:
        `select * from $thing`

        Args:
            thing: The table or record ID to select.

        Example:
            db.select('person')
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def create(
        self,
        thing: Union[str, RecordID, Table],
        data: Optional[Union[List[dict], dict]] = None,
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """Create a record in the database.

        This function will run the following query in the database:
        `create $thing content $data`

        Args:
            thing: The table or record ID.
            data (optional): The document / record data to insert.

        Example:
            db.create
        """
        raise NotImplementedError(f"create not implemented for: {self}")

    async def update(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """Update all records in a table, or a specific record, in the database.

        This function replaces the current document / record data with the
        specified data.

        This function will run the following query in the database:
        `update $thing content $data`

        Args:
            thing: The table or record ID.
            data (optional): The document / record data to insert.

        Example:
            Update all records in a table
                person = await db.update('person')

            Update a record with a specific ID
                record = await db.update('person:tobie', {
                    'name': 'Tobie',
                    'settings': {
                        'active': true,
                        'marketing': true,
                        },
                })
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def upsert(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """Insert records into the database, or to update them if they exist.


        This function will run the following query in the database:
        `upsert $thing content $data`

        Args:
            thing: The table or record ID.
            data (optional): The document / record data to insert.

        Example:
            Insert or update all records in a table
                person = await db.upsert('person')

            Insert or update a record with a specific ID
                record = await db.upsert('person:tobie', {
                    'name': 'Tobie',
                    'settings': {
                        'active': true,
                        'marketing': true,
                        },
                })
        """
        raise NotImplementedError(f"upsert not implemented for: {self}")

    async def merge(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """Modify by deep merging all records in a table, or a specific record, in the database.

        This function merges the current document / record data with the
        specified data.

        This function will run the following query in the database:
        `update $thing merge $data`

        Args:
            thing: The table name or the specific record ID to change.
            data (optional): The document / record data to insert.

        Example:
            Update all records in a table
                people = await db.merge('person', {
                    'updated_at':  str(datetime.datetime.utcnow())
                    })

            Update a record with a specific ID
                person = await db.merge('person:tobie', {
                    'updated_at': str(datetime.datetime.utcnow()),
                    'settings': {
                        'active': True,
                        },
                    })

        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def patch(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """Apply JSON Patch changes to all records, or a specific record, in the database.

        This function patches the current document / record data with
        the specified JSON Patch data.

        This function will run the following query in the database:
        `update $thing patch $data`

        Args:
            thing: The table or record ID.
            data: The data to modify the record with.

        Example:
            Update all records in a table
                people = await db.patch('person', [
                    { 'op': "replace", 'path': "/created_at", 'value': str(datetime.datetime.utcnow()) }])

            Update a record with a specific ID
            person = await db.patch('person:tobie', [
                { 'op': "replace", 'path': "/settings/active", 'value': False },
                { 'op': "add", "path": "/tags", "value": ["developer", "engineer"] },
                { 'op': "remove", "path": "/temp" },
            ])
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def delete(
        self, thing: Union[str, RecordID, Table]
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """Delete all records in a table, or a specific record, from the database.

        This function will run the following query in the database:
        `delete $thing`

        Args:
            thing: The table name or a RecordID to delete.

        Example:
            Delete a specific record from a table
                await db.delete(RecordID('person', 'h5wxrf2ewk8xjxosxtyc'))

            Delete all records from a table
                await db.delete('person')
        """
        raise NotImplementedError(f"delete not implemented for: {self}")

    async def info(self) -> Coroutine[Any, Any, dict]:
        """This returns the record of an authenticated record user.

        Example:
            await db.info()
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def insert(
        self, table: Union[str, Table], data: Union[List[dict], dict]
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """
        Inserts one or multiple records in the database.

        This function will run the following query in the database:
        `INSERT INTO $thing $data`

        Args:
            table: The table name to insert records in to
            data: Either a single document/record or an array of documents/records to insert

        Example:
            await db.insert('person', [{ name: 'Tobie'}, { name: 'Jaime'}])

        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def insert_relation(
        self, table: Union[str, Table], data: Union[List[dict], dict]
    ) -> Coroutine[Any, Any, Union[List[dict], dict]]:
        """
        Inserts one or multiple relations in the database.

        This function will run the following query in the database:
        `INSERT RELATION INTO $table $data`

        Args:
            table: The table name to insert records in to
            data: Either a single document/record or an array of documents/records to insert

        Example:
            await db.insert_relation('likes', { in: person:1, id: 'object', out: person:2})

        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def live(
        self, table: Union[str, Table], diff: bool = False
    ) -> Coroutine[Any, Any, UUID]:
        """Initiates a live query for a specified table name.

        Args:
            table: The table name to listen for changes for.
            diff: If unset to true, live notifications will include
            an array of JSON Patch objects, rather than
            the entire record for each notification. Defaults to false.

        Returns:
            The live query uuid

        Example:
            await db.live('person')
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def subscribe_live(
        self, query_uuid: Union[str, UUID]
    ) -> Coroutine[Any, Any, Queue]:
        """Returns a queue that receives notification messages from a running live query.

        Args:
            query_uuid: The uuid for the live query

        Returns:
            the notification queue

        Example:
            await db.subscribe_live(UUID)
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def kill(self, query_uuid: Union[str, UUID]) -> Coroutine[Any, Any, None]:
        """Kills a running live query by it's UUID.

        Args:
            query_uuid: The UUID of the live query you wish to kill.

        Example:
            await db.kill(UUID)

        """
        raise NotImplementedError(f"query not implemented for: {self}")
