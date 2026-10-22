import os
from uuid import UUID

import httpx
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

server = MCPServer("S(AI)pport scoped support tools", version="0.1.0", log_level="WARNING")
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


async def forward(name, arguments):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            os.environ["SUPPORT_API_URL"] + "/api/internal/tools",
            headers={"Authorization": "Bearer " + os.environ["SUPPORT_CONTEXT"]},
            json={"name": name, "arguments": arguments},
        )
        r.raise_for_status()
        return r.json()


@server.tool(annotations=READ)
async def get_account_context() -> dict:
    """Read only the current ticket account."""
    return await forward("get_account_context", {})


@server.tool(annotations=READ)
async def get_billing_state() -> dict:
    """Read the scoped billing event and payment evidence."""
    return await forward("get_billing_state", {})


@server.tool(annotations=READ)
async def get_delivery_state() -> dict:
    """Read the scoped integration event and delivery attempts."""
    return await forward("get_delivery_state", {})


@server.tool(annotations=READ)
async def search_documentation(query: str) -> dict:
    """Search authorized, applicable documentation."""
    return await forward("search_documentation", {"query": query})


@server.tool(annotations=READ)
async def read_document(document_id: UUID) -> dict:
    """Read an exact authorized document source."""
    return await forward("read_document", {"document_id": str(document_id)})


@server.tool(annotations=WRITE)
async def propose_action(kind: str, target_id: str) -> dict:
    """Create a policy-checked proposal; never approve or execute."""
    return await forward("propose_action", {"kind": kind, "target_id": target_id})


@server.tool(annotations=WRITE)
async def finish_investigation(
    disposition: str,
    summary: str,
    facts: list[str],
    missing_information: list[str],
    source_ids: list[str],
    reply: str,
    assumptions: list[str] | None = None,
) -> dict:
    """Save a structured conclusion with exact evidence references."""
    return await forward(
        "finish_investigation",
        {
            "disposition": disposition,
            "summary": summary,
            "facts": facts,
            "assumptions": assumptions or [],
            "missing_information": missing_information,
            "source_ids": source_ids,
            "reply": reply,
        },
    )


if __name__ == "__main__":
    server.run(transport="stdio")
