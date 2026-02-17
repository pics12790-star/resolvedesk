"""A real MCP stdio server, with run-scoped capabilities instead of customer-supplied IDs."""

from mcp.server.fastmcp import FastMCP
from resolvedesk import store
import logging

logging.getLogger("mcp").setLevel(logging.WARNING)

mcp = FastMCP("ResolveDesk demo commerce")


@mcp.tool()
def get_order(capability: str) -> dict:
    """Read the order bound to this authenticated support run."""
    return store.read_tool("get_order", capability)


@mcp.tool()
def get_shipment(capability: str) -> dict:
    """Read current delivery status and lateness for this run's order."""
    return store.read_tool("get_shipment", capability)


@mcp.tool()
def get_refund_status(capability: str) -> dict:
    """Read the refund ledger and existing replacement for the run's order."""
    return store.read_tool("get_refund_status", capability)


@mcp.tool()
def get_inventory(capability: str) -> dict:
    """Check replacement inventory for the run's product."""
    return store.read_tool("get_inventory", capability)


@mcp.tool()
def get_ticket_history(capability: str) -> dict:
    """Read recent tickets belonging to the authenticated run customer."""
    return store.read_tool("get_ticket_history", capability)


@mcp.tool()
def execute_approved_resolution(capability: str, approval_id: str) -> dict:
    """Execute exactly one persisted approved remedy. The server revalidates all rules."""
    return store.execute_action(capability, approval_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
