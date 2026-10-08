#!/usr/bin/env python3
"""
kensho japan-ec-apify MCP server — wraps specific Apify actors for Japanese e-commerce data.

Tools:
  - run_mercari_scraper: Search Mercari Japan for keyword
  - run_yahoo_auctions_scraper: Search Yahoo! Auctions Japan for keyword
  - run_rakuten_scraper: Search Rakuten Market for keyword
  - run_suumo_scraper: Search SUUMO for real estate listings
  - run_kakaku_scraper: Search Kakaku.com for price data
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

from fastmcp import FastMCP

server = FastMCP("japan-ec-apify-mcp")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_API_BASE = "https://api.apify.com/v2"

def _apify_actor_call(actor_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
    """Helper to run an Apify actor and return the run info."""
    if not APIFY_TOKEN:
        return {"error": "APIFY_TOKEN not set in environment"}
    try:
        import urllib.request
        body = json.dumps({"input": input_data or {}, "waitSecs": 30}).encode()
        req = urllib.request.Request(
            f"{APIFY_API_BASE}/runs?actionStarts={actor_id}",
            data=body,
            headers={
                "Authorization": f"Bearer {APIFY_TOKEN}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return {
                "runId": data.get("id"),
                "actorRunId": data.get("id"),
                "status": data.get("status"),
                "data": data
            }
    except Exception as e:
        return {"error": str(e)}

@server.tool()
def run_mercari_scraper(keyword: str, limit: Optional[int] = None) -> dict[str, Any]:
    """Search Mercari Japan for keyword using the mercari-japan-search-scraper actor."""
    actor_id = "fruitful_quintessence/mercari-japan-search-scraper"
    input_data = {"keyword": keyword}
    if limit is not None:
        input_data["limit"] = limit
    return _apify_actor_call(actor_id, input_data)

@server.tool()
def run_yahoo_auctions_scraper(keyword: str, limit: Optional[int] = None) -> dict[str, Any]:
    """Search Yahoo! Auctions Japan for keyword using the yahoo-auctions-japan-scraper actor."""
    actor_id = "fruitful_quintessence/yahoo-auctions-japan-scraper"
    input_data = {"keyword": keyword}
    if limit is not None:
        input_data["limit"] = limit
    return _apify_actor_call(actor_id, input_data)

@server.tool()
def run_rakuten_scraper(keyword: str, limit: Optional[int] = None) -> dict[str, Any]:
    """Search Rakuten Market for keyword using the rakuten-market-scraper actor."""
    actor_id = "fruitful_quintessence/rakuten-market-scraper"
    input_data = {"keyword": keyword}
    if limit is not None:
        input_data["limit"] = limit
    return _apify_actor_call(actor_id, input_data)

@server.tool()
def run_suumo_scraper(keyword: str, limit: Optional[int] = None) -> dict[str, Any]:
    """Search SUUMO for real estate listings using the suumo-japan-real-estate-scraper actor."""
    actor_id = "fruitful_quintessence/suumo-japan-real-estate-scraper"
    input_data = {"keyword": keyword}
    if limit is not None:
        input_data["limit"] = limit
    return _apify_actor_call(actor_id, input_data)

@server.tool()
def run_kakaku_scraper(keyword: str, limit: Optional[int] = None) -> dict[str, Any]:
    """Search Kakaku.com for price data using the japan-kakaku-price-scraper actor."""
    actor_id = "fruitful_quintessence/japan-kakaku-price-search"
    input_data = {"keyword": keyword}
    if limit is not None:
        input_data["limit"] = limit
    return _apify_actor_call(actor_id, input_data)

if __name__ == "__main__":
    server.run(transport=sys.argv[1] if len(sys.argv) > 1 else "stdio")