import os

from mcp.server.fastmcp import FastMCP
from models import MemoryParameters
from services import MemoryService

mcp = FastMCP("mem0-server")
memory_service = MemoryService(os.getenv("MEM0_USER_ID", "default_user_id"))


@mcp.tool()
def handle_memory(payload: MemoryParameters) -> str:
    """
    Handle memory operations such as adding and retrieving memories.

    Returns:
        str: Confirmation message or retrieved memories.
    """
    if payload.action == "add":
        memory_service.add_memory(payload.user_id, payload.memory)
        return "Memory added successfully."
    elif payload.action == "get":
        memories = memory_service.get_memories(payload.user_id)
        return memories
    else:
        return "Invalid action."


if __name__ == "__main__":
    mcp.run(transport="stdio")
