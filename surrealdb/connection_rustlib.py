import rust_surrealdb

from surrealdb.connection import Connection


class RustLibConnection(Connection):
    async def connect(self):
        print(rust_surrealdb.sum_as_string())
        self._connection = await self._make_connection(url=self.url)
