"""Bounded retention for disposable, expired demo workspaces."""


async def expire_workspaces(db, lab):
    rows = await db.all("""SELECT t.id FROM tenants t
        WHERE EXISTS(SELECT 1 FROM sessions s WHERE s.tenant_id=t.id)
        AND NOT EXISTS(SELECT 1 FROM sessions s WHERE s.tenant_id=t.id AND s.expires_at>now())
        AND NOT EXISTS(SELECT 1 FROM runs r WHERE r.tenant_id=t.id AND r.status IN ('queued','running'))
        ORDER BY t.created_at LIMIT 20""")
    for row in rows:
        tenant = row["id"]
        # Lab removal is idempotent; a product-DB failure is retried next cycle.
        response = await lab.client.delete(f"/tenants/{tenant}")
        response.raise_for_status()
        async with db.pool.connection() as c, c.transaction():
            for table in ("events", "audit", "actions"):
                await c.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))
            await c.execute(
                "DELETE FROM model_calls WHERE run_id IN (SELECT id FROM runs WHERE tenant_id=%s)", (tenant,)
            )
            for table in ("runs", "tickets", "documents", "sessions", "actors"):
                await c.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))
            await c.execute("DELETE FROM tenants WHERE id=%s", (tenant,))
    await db.execute("DELETE FROM rate_limits WHERE expires_at<now()")
    return len(rows)
