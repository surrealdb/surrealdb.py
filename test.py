import asyncio

from surrealdb.data.types.geometry import GeometryPoint, GeometryLine
from surrealdb.data.types.table import Table
from surrealdb.data.cbor import encode, decode

from surrealdb.connection.http import HTTPConnection
from surrealdb.connection.ws import WebsocketConnection
from surrealdb.async_surrealdb import AsyncSurrealDB


def test_cbor():
    point1 = GeometryPoint(latitude=10.00, longitude=-3.21)
    point2 = GeometryPoint(latitude=3.10, longitude=0.1)

    line1 = GeometryLine([point1, point2])

    table = Table('testtable')

    person = {
        'name': 'Remi',
        'location': point2
    }

    data1 = encode(point1)
    data2 = encode(line1)
    data3 = encode(table)
    data4 = encode(person)

    print('Encoded 1:', data1.hex())
    print('Encoded 2:', data2.hex())
    print('Encoded 3:', data3.hex())
    print('Encoded 4:', data4.hex())

    print('Decoded 1:', decode(data1))
    print('Decoded 4:', decode(data4))


async def test_make_request_ws():
    ws_con = WebsocketConnection(base_url='ws://localhost:8000', namespace='test', database='test')
    await ws_con.connect()
    await ws_con.send('signin', {'user': 'root', 'pass': 'root'})


async def test_make_request_http():
    http_con = HTTPConnection(base_url='http://localhost:8000', namespace='test', database='test')
    await http_con.connect()
    await http_con.send('signin', {'user': 'root', 'pass': 'root'})


async def test_db_http():
    db = AsyncSurrealDB('http://localhost:8000')
    await db.connect()
    await db.use('test', 'test')
    token = await db.sign_in('root', 'root')

    print(token)
    await db.close()


async def test_db_ws():
    async with AsyncSurrealDB('http://127.0.0.1:8000') as db:
        await db.use('test', 'test')
        token = await db.sign_in('root', 'root')

        await db.authenticate(token)
        # await db.invalidate(token)
        await db.info()
        await db.version()


asyncio.run(test_db_ws())
# test_cbor()
