#!/usr/bin/env python3
"""MLIT Property Transaction Prices — MCP Server (FastMCP).

Wraps the published Apify actor `fruitful_quintessence/mlit-japan-property-prices`
as an MCP tool so AI agents can query Japanese real-estate transaction prices
from the MLIT Reinfolib XIT001 API.

Companion to japan-property-hazard-mcp (disaster risk). Together they cover
the two MLIT datasets that matter for Japan property investment screening.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastmcp import FastMCP

server = FastMCP("mlit-property-prices")

ACTOR_NAME = "mlit-japan-property-prices"
APIFY_API_BASE = "https://api.apify.com/v2"


def _token() -> str:
    return os.environ.get("APIFY_TOKEN", "").strip()


def _run_actor(input_data: dict[str, Any]) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    token = _token()
    if not token:
        return {"error": "APIFY_TOKEN not set in environment"}

    body = json.dumps({"input": input_data}).encode()
    req = urllib.request.Request(
        f"{APIFY_API_BASE}/acts/{ACTOR_NAME}/runs",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"error": f"Apify API {exc.code}: {exc.read().decode(errors='replace')[:400]}"}

    run_id = (data.get("data") or {}).get("id")
    return {"runId": run_id, "status": "started"}


def _fetch_dataset(run_id: str, limit: int) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    token = _token()
    if not token:
        return {"error": "APIFY_TOKEN not set"}

    req = urllib.request.Request(
        f"{APIFY_API_BASE}/actor-runs/{run_id}/dataset/items?limit={limit}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"error": f"Apify API {exc.code}: {exc.read().decode(errors='replace')[:400]}"}

    items = (data.get("data") or {}).get("items", []) if isinstance(data, dict) else data
    return {"runId": run_id, "count": len(items), "items": items[:limit]}


@server.tool()
def query_property_prices(
    prefecture_code: str | None = None,
    year_from: int = 2005,
    year_to: int = 2026,
    quarter_from: int = 1,
    quarter_to: int = 4,
    price_classification: str = "01",
    language: str = "en",
    max_requests: int = 50,
    limit: int = 1000,
) -> dict[str, Any]:
    """Query Japanese real-estate transaction prices from the official MLIT XIT001 API.

    Covers all 47 prefectures, 2005-Q3 to present. Returns one record per
    transaction with price (total / per sqm), area, floor plan, building year,
    structure, use, road frontage and city-planning fields as clean JSON.

    Args:
        prefecture_code: Two-digit prefecture code (e.g. "13" = Tokyo). Omit for all 47.
        year_from / year_to: Range bounds, 2005-2026.
        quarter_from / quarter_to: 1-4.
        price_classification: "01" transaction prices (default), "02" contract prices, "" both.
        language: "en" (default, international buyers) or "ja".
        max_requests: Safety cap on upstream MLIT API calls.
        limit: Max dataset records returned.
    """
    input_data: dict[str, Any] = {
        "yearFrom": year_from,
        "yearTo": year_to,
        "quarterFrom": quarter_from,
        "quarterTo": quarter_to,
        "priceClassification": price_classification,
        "language": language,
        "maxRequests": max_requests,
    }
    if prefecture_code:
        input_data["prefectureCodes"] = [prefecture_code]
    return _run_actor(input_data)


@server.tool()
def get_run_results(run_id: str, limit: int = 1000) -> dict[str, Any]:
    """Fetch the dataset produced by a run started via query_property_prices."""
    return _fetch_dataset(run_id, limit)


if __name__ == "__main__":
    server.run()