#!/usr/bin/env python3
"""Test the MCP server tools via stdio probe."""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcp.client.stdio import stdio_client
from mcp import ClientSession

async def test_tools():
    async with stdio_client(server_params={"command": "python", "args": ["server/server.py"]}) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Test current_sweep
            result = await session.call_tool("current_sweep", {"keyword": "Amazon"})
            print("=== current_sweep ===")
            print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
            
            # Test sweep_history
            result = await session.call_tool("sweep_history", {"keyword": "Amazon", "limit": 5})
            print("\n=== sweep_history ===")
            print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
            
            # Test top_prize_movers
            result = await session.call_tool("top_prize_movers", {"direction": "both", "limit": 5})
            print("\n=== top_prize_movers ===")
            print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(test_tools())