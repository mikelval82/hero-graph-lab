from __future__ import annotations

import argparse
import asyncio
import json
from importlib.metadata import version
from typing import Any

from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from hero_graph_lab.explore.gateway import MCP_INSTRUCTIONS
from hero_graph_lab.mcp_bridge import DEFAULT_GRAPH_LAB_URL, GraphLabClient


def create_mcp_server(client: GraphLabClient) -> Server:
    server = Server(
        "hero-graph-lab",
        version=version("hero-graph-lab"),
        instructions=MCP_INSTRUCTIONS,
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        payload = await asyncio.to_thread(client.tools)
        return [
            types.Tool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"],
                annotations=types.ToolAnnotations.model_validate(tool["annotations"]),
            )
            for tool in payload.get("tools", [])
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        payload = await asyncio.to_thread(client.call_tool, name, arguments)
        content = payload.get("content")
        if not isinstance(content, str):
            content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=content)],
            structuredContent=payload,
            isError=False,
        )

    return server


async def run_mcp_server(client: GraphLabClient) -> None:
    server = create_mcp_server(client)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Expose the active HERO Graph Lab through MCP STDIO")
    parser.add_argument("--url", default=DEFAULT_GRAPH_LAB_URL, help="Loopback Graph Lab base URL")
    args = parser.parse_args()
    asyncio.run(run_mcp_server(GraphLabClient(args.url)))


if __name__ == "__main__":
    main()
