import re
from uuid import UUID

from app.db import Database


async def retrieve(
    db: Database,
    tenant: UUID | str,
    version: str,
    query: str,
    family: str | None = None,
    baseline: bool = False,
) -> list[dict]:
    """Version/topic-filtered lexical search, with a measured disjunctive fallback."""
    rows = await db.all(
        """SELECT id,source_key,title,version,body,
        ts_rank(search,websearch_to_tsquery('english',%s)) AS rank FROM documents
        WHERE tenant_id=%s AND product_version=%s AND search @@ websearch_to_tsquery('english',%s)
        AND (%s::text IS NULL OR family IN (%s,'shared'))
        ORDER BY rank DESC,source_key LIMIT 3""",
        (query, tenant, version, query, None if baseline else family, family),
    )
    if rows or baseline:
        return rows
    terms = re.findall(r"[a-zA-Z0-9_]+", query)[:24]
    if not terms:
        return []
    broad = " OR ".join(terms)
    return await db.all(
        """SELECT id,source_key,title,version,body,
        ts_rank(search,websearch_to_tsquery('english',%s)) AS rank FROM documents
        WHERE tenant_id=%s AND product_version=%s AND search @@ websearch_to_tsquery('english',%s)
        AND (%s::text IS NULL OR family IN (%s,'shared'))
        ORDER BY rank DESC,source_key LIMIT 3""",
        (broad, tenant, version, broad, family, family),
    )
