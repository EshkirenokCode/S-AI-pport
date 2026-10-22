import json

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool


def clean(value):
    return json.loads(json.dumps(value, default=str))


def js(value):
    return Jsonb(clean(value))


class Database:
    def __init__(self, url: str):
        self.pool = AsyncConnectionPool(url, open=False, min_size=1, max_size=10,
                                        kwargs={'autocommit': True, 'row_factory': dict_row})

    async def open(self):
        await self.pool.open(wait=True)

    async def close(self):
        await self.pool.close()

    async def one(self, query, args=()):
        async with self.pool.connection() as conn:
            return await (await conn.execute(query, args)).fetchone()

    async def all(self, query, args=()):
        async with self.pool.connection() as conn:
            return await (await conn.execute(query, args)).fetchall()

    async def execute(self, query, args=()):
        async with self.pool.connection() as conn:
            return await conn.execute(query, args)

    async def event(self, run, kind, title, data=None):
        return await self.one(
            'INSERT INTO events(tenant_id,run_id,kind,title,data) VALUES(%s,%s,%s,%s,%s) RETURNING id',
            (run['tenant_id'], run['id'], kind, title, js(data or {})))

    async def audit(self, tenant, actor, verb, object_id, trace=None):
        await self.execute('INSERT INTO audit(tenant_id,actor_id,verb,object_id,trace_id) VALUES(%s,%s,%s,%s,%s)',
                           (tenant, actor, verb, str(object_id), trace))
