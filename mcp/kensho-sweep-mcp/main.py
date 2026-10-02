"""kensho-sweep-mcp Apify Standby entrypoint.

Runs the read-only kensho sweepstakes MCP server as a Streamable HTTP
endpoint on Apify (APIFY_CONTAINER_PORT), so AI agents can discover it
via the Apify Store / Smithery / Glama without any API key.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

import uvicorn

logging.basicConfig(level=logging.INFO)

if os.environ.get("APIFY_CONTAINER_PORT"):
    from apify import Actor
else:
    raise SystemExit("APIFY_CONTAINER_PORT 未設定: Apifyランタイムで実行してください")

from server import server as mcp_server  # type: ignore[import-not-found]


async def main() -> None:
    async with Actor:
        port = int(os.environ.get("APIFY_CONTAINER_PORT", "3000"))
        app = mcp_server.http_app(transport="streamable-http")
        Actor.log.info(f"kensho-sweep-mcp MCP server 起動 (port {port})")
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        uvicorn_server = uvicorn.Server(config)
        try:
            await uvicorn_server.serve()
        except asyncio.CancelledError:
            Actor.log.info("kensho-sweep-mcp MCP server 停止")


if __name__ == "__main__":
    asyncio.run(main())