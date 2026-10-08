import sys
sys.path.insert(0, '.')
from server import server
import asyncio
async def main():
    tools = await server._list_tools()
    for t in tools:
        print(t.name)
asyncio.run(main())
