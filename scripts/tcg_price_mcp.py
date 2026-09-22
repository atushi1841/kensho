#!/usr/bin/env python3
"""tcg-price-mcp: FastMCP server for the Japan TCG used-price trend dataset.

Mirrors the `japan-market-mcp` pattern (FastMCP tools, structured + text
output). Data is read from the accumulated kensho dataset (data/tcg_dataset/),
so this exposes a value-movement query API for AI agents / LLM tools:
  - tcg_current_price   → current used/new/list price for an item
  - tcg_price_history   → time series (trend) for an item
  - tcg_top_movers      → biggest used-price moves (uptrend / downtrend)

Run:  uvicorn tcg_price_mcp:app  (fastapi-mcp mounts the tools over HTTP)
or    python tcg_price_mcp.py --serve-mcp   (stdio MCP)
FastAPI app is exposed at /mcp as FastMCP+fastapi, and /health for liveness.
"""
from __future__ import annotations

from typing import Any, Optional

from fastmcp import FastMCP

from scripts.tcg_price_query import (
    current_price,
    load_observations,
    price_history,
    top_movers,
)

server = FastMCP("tcg-price-query")


def _load() -> list[dict[str, Any]]:
    return load_observations()


@server.tool()
async def tcg_current_price(item: str) -> dict[str, Any]:
    """Current used/new/list price for a Pokemon/TCG item in the Japan (Suruga-ya) dataset.

    Args:
        item: item name or URL substring (e.g. "リザードン", "pokemon card").
    Returns the latest observed price snapshot (JPY) plus match count.
    """
    return current_price(_load(), item)


@server.tool()
async def tcg_price_history(item: str, limit: int = 50) -> dict[str, Any]:
    """Price time series (trend) for an item in the Japan TCG used-price dataset.

    Args:
        item: item name or URL substring.
        limit: max number of history rows to return (default 50).
    Returns oldest-first observations of used/new/list prices (JPY).
    """
    return price_history(_load(), item, limit=limit)


@server.tool()
async def tcg_top_movers(direction: Optional[str] = None, limit: int = 10) -> dict[str, Any]:
    """Biggest used-price movers in the Japan TCG dataset (ranked by |delta JPY|).

    Args:
        direction: None/"both" = up+down, "up" = price rose, "down" = price fell.
        limit: max movers to return (default 10).
    """
    return top_movers(_load(), direction=direction, limit=limit)


if __name__ == "__main__":
    import sys

    if "--http" in sys.argv:
        # FastMCP native streamable-HTTP transport (single shared endpoint at /mcp)
        server.run(transport="streamable-http")
    else:
        server.run(transport="stdio")
