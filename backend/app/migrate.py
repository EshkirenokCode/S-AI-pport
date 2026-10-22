import asyncio
import hashlib
from pathlib import Path

from app.db import Database
from app.settings import settings


async def migrate():
    cfg = settings()
    for name, url in [("product", cfg.database_url), ("sandbox", cfg.sandbox_database_url)]:
        db = Database(url)
        await db.open()
        try:
            async with db.pool.connection() as c, c.transaction():
                await c.execute("SELECT pg_advisory_xact_lock(783125)")
                await c.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY, digest text NOT NULL, applied_at timestamptz DEFAULT now())"
                )
                for p in sorted((Path(__file__).parent / "migrations" / name).glob("*.sql")):
                    sql = p.read_text()
                    digest = hashlib.sha256(sql.encode()).hexdigest()
                    old = await (
                        await c.execute("SELECT digest FROM schema_migrations WHERE name=%s", (p.name,))
                    ).fetchone()
                    if old:
                        if old["digest"] != digest:
                            raise RuntimeError(f"Migration checksum mismatch: {name}/{p.name}")
                        continue
                    await c.execute(sql)
                    await c.execute(
                        "INSERT INTO schema_migrations(name,digest) VALUES(%s,%s)", (p.name, digest)
                    )
                    print(f"Applied {name}/{p.name}")
        finally:
            await db.close()


if __name__ == "__main__":
    asyncio.run(migrate())
