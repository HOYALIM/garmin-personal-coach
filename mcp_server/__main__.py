import json
import sys

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

from garmin_coach._version import __version__
from mcp_server.server import TOOLS, handle_tool_call


async def main():
    server = Server("garmin-personal-coach")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = handle_tool_call(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            options,
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
