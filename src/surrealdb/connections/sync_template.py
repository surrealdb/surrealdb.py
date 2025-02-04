from asyncio import Queue
from typing import Optional, List, Dict, Any, Union
from uuid import UUID

from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


class SyncTemplate:

    # def connect(self, url: str, options: Optional[Dict] = None) -> None:
    #     """Connects to a local or remote database endpoint.
    #
    #     Args:
    #         url: The url of the database endpoint to connect to.
    #         options: An object with options to initiate the connection to SurrealDB.
    #
    #     Example:
    #         # Connect to a remote endpoint
    #         db.connect('https://cloud.surrealdb.com/rpc');
    #
    #         # Specify a namespace and database pair to use
    #         db.connect('https://cloud.surrealdb.com/rpc', {
    #             namespace: 'surrealdb',
    #             database: 'docs',
    #         });
    #     """
    #     raise NotImplementedError(f"query not implemented for: {self}")

    def close(self) -> None:
        """Closes the persistent connection to the database.

        Example:
            db.close()
        """
        raise NotImplementedError(f"close not implemented for: {self}")

    def use(self, namespace: str, database: str) -> None:
        """Switch to a specific namespace and database.

        Args:
            namespace: Switches to a specific namespace.
            database: Switches to a specific database.

        Example:
            db.use('test', 'test')
        """
        raise NotImplementedError(f"use not implemented for: {self}")

    def authenticate(self, token: str) -> None:
        """Authenticate the current connection with a JWT token.

        Args:
            token: The JWT authentication token.

        Example:
            db.authenticate('insert token here')
        """
        raise NotImplementedError(f"authenticate not implemented for: {self}")

    def invalidate(self) -> None:
        """Invalidate the authentication for the current connection.

        Example:
            db.invalidate()
        """
        raise NotImplementedError(f"invalidate not implemented for: {self}")

    def signup(self, vars: Dict) -> str:
        """Sign this connection up to a specific authentication scope.
        [See the docs](https://surrealdb.com/docs/sdk/python/methods/signup)

        Args:
            vars: Variables used in a signup query.

        Example:
            db.signup({
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

    def signin(self, vars: Dict) -> str:
        """Sign this connection in to a specific authentication scope.
        [See the docs](https://surrealdb.com/docs/sdk/python/methods/signin)

        Args:
            vars: Variables used in a signin query.

        Example:
            db.signin({
                username: 'root',
                password: 'surrealdb',
            })
        """
        raise NotImplementedError(f"signin not implemented for: {self}")

    def let(self, key: str, value: Any) -> None:
        """Assign a value as a variable for this connection.

        Args:
            key: Specifies the name of the variable.
            value: Assigns the value to the variable name.

        Example:
            # Assign the variable on the connection
            db.let('name', {
                first: 'Tobie',
                last: 'Morgan Hitchcock',
            })

            # Use the variable in a subsequent query
            db.query('CREATE person SET name = $name')
        """
        raise NotImplementedError(f"let not implemented for: {self}")

    def unset(self, key: str) -> None:
        """Removes a variable for this connection.

        Args:
            key: Specifies the name of the variable.

        Example:
            db.unset('name')
        """
        raise NotImplementedError(f"let not implemented for: {self}")

    def query(self, query: str, vars: Optional[Dict] = None) -> Union[List[dict], dict]:
        """Run a set of SurrealQL statements against the database.

        Args:
            query: Specifies the SurrealQL statements.
            vars: Assigns variables which can be used in the query.

        Example:
            db.query(
                'CREATE person SET name = "John"; SELECT * FROM type::table($tb);',
                { tb: 'person' }
            )
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    def select(self, thing: Union[str, RecordID, Table]) -> Union[List[dict], dict]:
        """Select all records in a table (or other entity),
        or a specific record, in the database.

        This function will run the following query in the database:
        `select * from $thing`

        Args:
            thing: The table or record ID to select.

        Example:
            db.select('person')
        """
        raise NotImplementedError(f"select not implemented for: {self}")

    def create(
        self,
        thing: Union[str, RecordID, Table],
        data: Optional[Union[Union[List[dict], dict], dict]] = None,
    ) -> Union[List[dict], dict]:
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

    def update(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
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
                person = db.update('person')

            Update a record with a specific ID
                record = db.update('person:tobie', {
                    'name': 'Tobie',
                    'settings': {
                        'active': true,
                        'marketing': true,
                        },
                })
        """
        raise NotImplementedError(f"update not implemented for: {self}")

    def upsert(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
        """Insert records into the database, or to update them if they exist.


        This function will run the following query in the database:
        `upsert $thing content $data`

        Args:
            thing: The table or record ID.
            data (optional): The document / record data to insert.

        Example:
            Insert or update all records in a table
                person = db.upsert('person')

            Insert or update a record with a specific ID
                record = db.upsert('person:tobie', {
                    'name': 'Tobie',
                    'settings': {
                        'active': true,
                        'marketing': true,
                        },
                })
        """
        raise NotImplementedError(f"upsert not implemented for: {self}")

    def merge(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
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
                people = db.merge('person', {
                    'updated_at':  str(datetime.datetime.utcnow())
                    })

            Update a record with a specific ID
                person = db.merge('person:tobie', {
                    'updated_at': str(datetime.datetime.utcnow()),
                    'settings': {
                        'active': True,
                        },
                    })

        """
        raise NotImplementedError(f"merge not implemented for: {self}")

    def patch(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
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
                people = db.patch('person', [
                    { 'op': "replace", 'path': "/created_at", 'value': str(datetime.datetime.utcnow()) }])

            Update a record with a specific ID
            person = db.patch('person:tobie', [
                { 'op': "replace", 'path': "/settings/active", 'value': False },
                { 'op': "add", "path": "/tags", "value": ["developer", "engineer"] },
                { 'op': "remove", "path": "/temp" },
            ])
        """
        raise NotImplementedError(f"patch not implemented for: {self}")

    def delete(self, thing: Union[str, RecordID, Table]) -> Union[List[dict], dict]:
        """Delete all records in a table, or a specific record, from the database.

        This function will run the following query in the database:
        `delete $thing`

        Args:
            thing: The table name or a RecordID to delete.

        Example:
            Delete a specific record from a table
                db.delete(RecordID('person', 'h5wxrf2ewk8xjxosxtyc'))

            Delete all records from a table
                db.delete('person')
        """
        raise NotImplementedError(f"delete not implemented for: {self}")

    def info(self) -> dict:
        """This returns the record of an authenticated record user.

        Example:
            db.info()
        """
        raise NotImplementedError(f"info not implemented for: {self}")

    def insert(
        self, table: Union[str, Table], data: Union[List[dict], dict]
    ) -> Union[List[dict], dict]:
        """
        Inserts one or multiple records in the database.

        This function will run the following query in the database:
        `INSERT INTO $thing $data`

        Args:
            table: The table name to insert records in to
            data: Either a single document/record or an array of documents/records to insert

        Example:
            db.insert('person', [{ name: 'Tobie'}, { name: 'Jaime'}])

        """
        raise NotImplementedError(f"insert not implemented for: {self}")

    def insert_relation(
        self, table: Union[str, Table], data: Union[List[dict], dict]
    ) -> Union[List[dict], dict]:
        """
        Inserts one or multiple relations in the database.

        This function will run the following query in the database:
        `INSERT RELATION INTO $table $data`

        Args:
            table: The table name to insert records in to
            data: Either a single document/record or an array of documents/records to insert

        Example:
            db.insert_relation('likes', { in: person:1, id: 'object', out: person:2})

        """
        raise NotImplementedError(f"insert_relation not implemented for: {self}")

    def live(self, table: Union[str, Table], diff: bool = False) -> UUID:
        """Initiates a live query for a specified table name.

        Args:
            table: The table name to listen for changes for.
            diff: If set to true, live notifications will include
            an array of JSON Patch objects, rather than
            the entire record for each notification. Defaults to false.

        Returns:
            The live query uuid

        Example:
            db.live('person')
        """
        raise NotImplementedError(f"live not implemented for: {self}")

    def subscribe_live(self, query_uuid: Union[str, UUID]) -> Queue:
        """Live notification returns a queue that receives notification messages from the back end.

        Args:
            query_uuid: The uuid for the live query

        Returns:
            the notification queue

        Example:
            db.subscribe_live(UUID)
        """
        raise NotImplementedError(f"subscribe_live not implemented for: {self}")

    def kill(self, query_uuid: Union[str, UUID]) -> None:
        """Kills a running live query by it's UUID.

        Args:
            query_uuid: The UUID of the live query you wish to kill.

        Example:
            db.kill(UUID)

        """
        raise NotImplementedError(f"kill not implemented for: {self}")
