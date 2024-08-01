# Testing

This testing suite is mainly used to test the python SDK and how it runs against multiple different versions of
SurrealDB for the following variances:

### Python versions

- 3.7
- 3.8
- 3.9
- 3.10

These all get tested for the last 4 versions of SurrealDB, with blocking and async clients, and websocket and http
protocols. At the time of writing this, it results in 960 tests but will quickly be increasing.

## Atomic Testing
Python is an ideal choice for these tests due to Python not supporting multithreading through the GIL. This means
that we can only run one request to the database at a time even though we are running multiple tests. Each test
has a `setUp` and `tearDown` method as seen below:

```python
def setUp(self):
    self.connection = SurrealDB(Url().url)
    self.queries: List[str] = []

    self.connection.signin({
        "username": "root",
        "password": "root",
    })

def tearDown(self):
    for query in self.queries:
        self.connection.query(query)
```
Here we are see that the `setUp` method creates a new connection to the database and signs in with the root user. The
`tearDown` method then runs all the queries that were run in the test at the start of a test so when the test finishes
or breaks, the teardown queries are run to clean up the database. This means that the state of the database is clear
at the start of every test no matter what order we run or if we run a test individually when developing a new feature.
An example test of the class having these setup and teardown methods is below:

```python
def test_update_ql(self):
    self.queries = ["DELETE user;"]
    self.connection.query("CREATE user:tobie SET name = 'Tobie';")
    self.connection.query("CREATE user:jaime SET name = 'Jaime';")
    outcome = self.connection.query("UPDATE user SET lastname = 'Morgan Hitchcock';")
    self.assertEqual(
        [
            {'id': 'user:jaime', "lastname": "Morgan Hitchcock", 'name': 'Jaime'},
            {'id': 'user:tobie', "lastname": "Morgan Hitchcock", 'name': 'Tobie'}
        ],
        outcome
    )
```
Here we can see that the `test_update_ql` method is setting the `self.queries` variable to `["DELETE user;"]` which
wipes the user table at the end of the test or if the test breaks. The test then creates two users, updates the
lastname of all users and then checks that the users have been updated correctly. This is a simple example but we can
run it as many times as we want and it will always work as expected. The test after this test might also do something
to the user table, but it will always be in the same state at the start of the test.

## Different SurrealDB Versions
The tests are run against the last 4 versions of SurrealDB. This is to ensure that the SDK is always compatible with
the latest version of SurrealDB and that it is also backwards compatible. We can define the protocol and surrealDB
version based on the environment variables `CONNECTION_PROTOCOL` and `CONNECTION_PORT`. The default values are `http`
and `8000` which is the latest version so there is no need to set these values unless you want to test against a
different protocol or older version. You can run the tests with the following command:

```bash
# testing all the http async and blocking for last five versions for http
export CONNECTION_PROTOCOL="http"
python -m unittest discover
export CONNECTION_PORT="8121"
python -m unittest discover
export CONNECTION_PORT="8120"
python -m unittest discover
export CONNECTION_PORT="8101"
python -m unittest discover
export CONNECTION_PORT="8111"
python -m unittest discover

# testing all the ws async and blocking for last five versions for websocket
export CONNECTION_PROTOCOL="ws"
export CONNECTION_PORT="8000"
python -m unittest discover
export CONNECTION_PORT="8121"
python -m unittest discover
export CONNECTION_PORT="8120"
python -m unittest discover
export CONNECTION_PORT="8101"
python -m unittest discover
export CONNECTION_PORT="8111"
python -m unittest discover
```
