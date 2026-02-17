import asyncio
import json
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from resolvedesk.config import ROOT, RUNTIME
from resolvedesk.tracing import traceable

READ_TOOLS = {"get_order", "get_shipment", "get_refund_status", "get_inventory", "get_ticket_history"}


@traceable(name="mcp_call_tools", run_type="tool", tags=["mcp", "commerce-tools"])
async def call_tools(calls):
    # Do not pass model API keys into a subprocess that only needs store access.
    env = {
        k: os.environ[k]
        for k in ("SYSTEMROOT", "PATH", "TEMP", "TMP", "DATABASE_URL")
        if k in os.environ
    }
    env.update(PYTHONPATH=str(ROOT), RESOLVEDESK_RUNTIME=str(RUNTIME))
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "resolvedesk.mcp_server"], env=env, cwd=str(ROOT)
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            outputs = {}
            for name, arguments in calls:
                result = await asyncio.wait_for(session.call_tool(name, arguments), timeout=20)
                if result.isError:
                    raise ValueError("MCP tool rejected the operation")
                value = result.structuredContent
                if value is None:
                    value = json.loads(next(c.text for c in result.content if c.type == "text"))
                outputs[name] = value
            return outputs


@traceable(name="mcp_invoke", run_type="tool", tags=["mcp", "commerce-tools"])
def invoke(calls):
    return asyncio.run(call_tools(calls))
