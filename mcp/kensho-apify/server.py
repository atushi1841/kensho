#!/usr/bin/env python3
"""kensho-apify MCP server — wraps Apify Actors for on-demand data fetching.

Tools:
  - list_actors: List available Apify actors
  - run_actor: Run an Apify actor with input parameters
  - get_run: Get run status and results
  - get_dataset: Fetch dataset items from a run
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from fastmcp import FastMCP

server = FastMCP("kensho-apify")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_API_BASE = "https://api.apify.com/v2"


@server.tool()
def list_actors() -> list[dict[str, Any]]:
    """List all Apify actors owned by the user."""
    if not APIFY_TOKEN:
        return [{"error": "APIFY_TOKEN not set in environment"}]
    
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{APIFY_API_BASE}/users/me/acts?limit=50",
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            acts = data.get("data", [])
            return [
                {"id": a["id"], "name": a["name"], "userId": a.get("userId")}
                for a in acts
            ]
    except Exception as e:
        return [{"error": str(e)}]


@server.tool()
def run_actor(
    actor_id: str,
    input_data: Optional[dict[str, Any]] = None,
    timeout_seconds: int = 300
) -> dict[str, Any]:
    """Run an Apify actor and return the run ID."""
    if not APIFY_TOKEN:
        return {"error": "APIFY_TOKEN not set in environment"}
    
    try:
        import urllib.request
        body = json.dumps({"input": input_data or {}, "waitSecs": timeout_seconds}).encode()
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
def get_run(run_id: str) -> dict[str, Any]:
    """Get status of an Apify actor run."""
    if not APIFY_TOKEN:
        return {"error": "APIFY_TOKEN not set in environment"}
    
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{APIFY_API_BASE}/runs/{run_id}",
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return {
                "runId": data.get("id"),
                "status": data.get("status"),
                "statusMessage": data.get("statusMessage"),
                "stats": data.get("stats")
            }
    except Exception as e:
        return {"error": str(e)}


@server.tool()
def get_dataset(run_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Get items from an Apify actor run's dataset."""
    if not APIFY_TOKEN:
        return []
    
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{APIFY_API_BASE}/runs/{run_id}/dataset/items?limit={limit}",
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("data", [])
    except Exception as e:
        return [{"error": str(e)}]


if __name__ == "__main__":
    server.run(transport=sys.argv[1] if len(sys.argv) > 1 else "stdio")
