import asyncio
from surrealdb import WebsocketClient
from pprint import pprint as pp

_URL = "ws://localhost:8000/rpc"
_NAMESPACE = "test"
_DATABASE = "test"
_USER = "root"
_PASS = "root"

async def main():
  async with WebsocketClient( url=_URL,
    namespace=_NAMESPACE, database=_DATABASE,
    username=_USER, password=_PASS,
  ) as session:
    while True:
      sql = input('SQL> ')
      if sql.upper() == 'Q': break        
      res = await session.query(sql)
      pp(res)

asyncio.run(main())
