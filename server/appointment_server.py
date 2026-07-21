from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from appointment_mcp import (
    decline_reschedule,
    get_current_appointment,
    get_patient,
    get_policy,
    get_provider,
    list_appointments,
    reschedule_appointment,
    search_available_slots,
)


mcp = FastMCP("appointment")

mcp.tool()(get_policy)
mcp.tool()(get_current_appointment)
mcp.tool()(get_patient)
mcp.tool()(get_provider)
mcp.tool()(search_available_slots)
mcp.tool()(reschedule_appointment)
mcp.tool()(decline_reschedule)
mcp.tool()(list_appointments)


if __name__ == "__main__":
    mcp.run(transport="stdio")
