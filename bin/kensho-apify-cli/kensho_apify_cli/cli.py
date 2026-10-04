#!/usr/bin/env python3
"""kensho-apify — CLI toolkit for Apify actors (Kensho portfolio).

Usage:
  kensho-apify list                    # List all actors
  kensho-apify list --category manga   # Filter by category
  kensho-apify info <actor-id>         # Show actor details
  kensho-apify run <actor-id>          # Trigger a test run
  kensho-apify stats <actor-id>        # Show stats/metrics
  kensho-apify search <keyword>        # Search actors by keyword
  kensho-apify seed                    # Generate sample input data
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

APIFY_API = "https://api.apify.com/v2"
ACTOR_SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "actor_priority_analysis.json")


def _get_token() -> str:
    """Read APIFY_TOKEN from env or .env file."""
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT", "")
    if token:
        return token.strip()
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line.startswith("APIFY_TOKEN=") or line.startswith("APIFY_TOKEN_DEFAULT="):
                    token = line.split("=", 1)[1].strip().strip('"')
                    if token:
                        return token
    return ""


def _api_get(path: str, token: str | None = None) -> dict:
    """Make a GET request to Apify API with Authorization header."""
    t = token or _get_token()
    sep = "&" if "?" in path else "?"
    url = f"{APIFY_API}{path}{sep}token={t}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"error": f"HTTP {e.code}", "body": body}
    except Exception as e:
        return {"error": str(e)}


def _api_post(path: str, payload: dict, token: str | None = None) -> dict:
    """Make a POST request to Apify API."""
    t = token or _get_token()
    sep = "&" if "?" in path else "?"
    url = f"{APIFY_API}{path}{sep}token={t}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Accept": "application/json"
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"error": f"HTTP {e.code}", "body": body}
    except Exception as e:
        return {"error": str(e)}


def _load_actors() -> list[dict]:
    """Load actor metadata from local snapshot."""
    if os.path.exists(ACTOR_SNAPSHOT):
        try:
            with open(ACTOR_SNAPSHOT, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def cmd_list(args: argparse.Namespace) -> int:
    """List actors, optionally filtered by category or keyword."""
    actors = _load_actors()
    if not actors:
        print("No actor data available. Run 'kensho-apify fetch' first.")
        return 1

    # Filter by category
    if args.category:
        cat = args.category.lower()
        actors = [a for a in actors if cat in (a.get("description") or "").lower()]

    # Filter by keyword
    if args.search:
        kw = args.search.lower()
        actors = [a for a in actors if kw in (a.get("name") or "").lower()
                  or kw in (a.get("title") or "").lower()
                  or kw in (a.get("description") or "").lower()]

    # Limit output
    limit = args.limit or len(actors)
    actors = actors[:limit]

    # Output format
    if args.json:
        print(json.dumps(actors, indent=2, ensure_ascii=False))
        return 0

    # Table output
    print(f"{'ID':<24} {'Name':<45} {'Runs':>6} {'Users':>6} {'Price':>8}")
    print("-" * 95)
    for a in actors:
        aid = a.get("id", "?")[:22]
        name = (a.get("name") or "?")[:43]
        runs = a.get("total_runs", 0)
        users = a.get("total_users", 0)
        price = a.get("price")
        price_str = f"${price}" if price else "-"
        print(f"{aid:<24} {name:<45} {runs:>6} {users:>6} {price_str:>8}")

    print(f"\nTotal: {len(actors)} actors")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show detailed info for an actor."""
    actors = _load_actors()
    actor = next((a for a in actors if a.get("id") == args.id or a.get("name") == args.id), None)

    if not actor:
        # Try fetching from API
        token = _get_token()
        if not token:
            print("Error: No API token found. Set APIFY_TOKEN in environment or .env file.")
            return 1
        print(f"Fetching info for {args.id} from Apify API...")
        result = _api_get(f"/acts/{args.id}")
        if "error" in result:
            print(f"Error: {result['error']}")
            return 1
        actor = result.get("data", result)

    if args.json:
        print(json.dumps(actor, indent=2, ensure_ascii=False))
        return 0

    print(f"Name:     {actor.get('name', 'N/A')}")
    print(f"ID:       {actor.get('id', 'N/A')}")
    print(f"Title:    {actor.get('title', 'N/A')}")
    print(f"Runs:     {actor.get('total_runs', actor.get('stats', {}).get('totalRuns', 'N/A'))}")
    print(f"Users:    {actor.get('total_users', actor.get('stats', {}).get('totalUsers', 'N/A'))}")
    print(f"Price:    ${actor.get('price', 'FREE') if actor.get('price') else 'FREE'} per 1K results")
    desc = actor.get("description", "")
    if desc:
        print(f"\nDescription:\n{desc}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Trigger a test run for an actor."""
    token = _get_token()
    if not token:
        print("Error: No API token found. Set APIFY_TOKEN in environment or .env file.")
        return 1

    actor_id = args.id
    print(f"Triggering run for actor {actor_id}...")

    payload = {"waitForFinish": 0}
    if args.timeout:
        payload["timeoutSecs"] = args.timeout

    result = _api_post(f"/acts/{actor_id}/runs", payload)
    if "error" in result:
        print(f"Error: {result['error']}")
        if "body" in result:
            print(result["body"])
        return 1

    data = result.get("data", result)
    run_id = data.get("id", "?")
    status = data.get("status", "?")
    print(f"Run started: {run_id}")
    print(f"Status: {status}")
    print(f"URL: https://api.apify.com/v2/acts/{actor_id}/runs/{run_id}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show current stats for an actor."""
    token = _get_token()
    if not token:
        print("Error: No API token found. Set APIFY_TOKEN in environment or .env file.")
        return 1

    actor_id = args.id
    print(f"Fetching stats for {actor_id}...")

    result = _api_get(f"/acts/{actor_id}")
    if "error" in result:
        print(f"Error: {result['error']}")
        return 1

    data = result.get("data", result)
    stats = data.get("stats", {})

    if args.json:
        print(json.dumps({"id": actor_id, **stats}, indent=2, ensure_ascii=False))
        return 0

    print(f"Actor: {data.get('name', 'N/A')}")
    print(f"Total Runs:      {stats.get('totalRuns', 0)}")
    print(f"Users (30d):     {stats.get('totalUsers30Days', 0)}")
    print(f"Bookmarks:       {stats.get('bookmarkCount', 0)}")
    print(f"Last Run:        {stats.get('lastRunStartedAt', 'Never')}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search actors from the local dataset."""
    actors = _load_actors()
    if not actors:
        print("No actor data available.")
        return 1

    keyword = args.keyword.lower()
    results = [a for a in actors
               if keyword in (a.get("name") or "").lower()
               or keyword in (a.get("title") or "").lower()
               or keyword in (a.get("description") or "").lower()]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    print(f"Found {len(results)} actors matching '{args.keyword}':\n")
    for a in results[:20]:
        print(f"  {a.get('name', '?'):<45} | {a.get('title', '')[:50]}")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    """Generate sample input data for testing actors."""
    output_dir = args.output or "."
    os.makedirs(output_dir, exist_ok=True)

    samples = {
        "japan-anime-figure-price-data": {
            "series": "Naruto",
            "limit": 10
        },
        "surugaya-japan-hobby-prices": {
            "category": "figures",
            "limit": 10
        },
        "mandarake-auction-scraper": {
            "keyword": "anime figure",
            "limit": 10
        },
        "dlsite-scraper": {
            "category": "anime",
            "limit": 10
        },
        "yahoo-auctions-japan-scraper": {
            "keyword": "figure",
            "limit": 10
        },
        "mercari-japan-search-scraper": {
            "keyword": "anime",
            "limit": 10
        },
    }

    for name, data in samples.items():
        out_path = os.path.join(output_dir, f"seed_{name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Created: {out_path}")

    print(f"\nGenerated {len(samples)} seed files in {output_dir}/")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch fresh actor data from Apify API."""
    token = _get_token()
    if not token:
        print("Error: No API token found. Set APIFY_TOKEN in environment or .env file.")
        return 1

    print("Fetching actor list from Apify API...")
    result = _api_get("/acts?my=true&limit=200")
    if "error" in result:
        print(f"Error: {result['error']}")
        return 1

    items = result.get("data", {}).get("items", [])
    actors = []
    for item in items:
        actors.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "title": item.get("title"),
            "description": item.get("description", "")[:200],
            "stats": item.get("stats", {}),
            "createdAt": item.get("createdAt"),
            "modifiedAt": item.get("modifiedAt"),
        })

    # Save to data directory
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, "apify_actors_fresh.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(actors, f, indent=2, ensure_ascii=False)

    print(f"Fetched {len(actors)} actors. Saved to {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="kensho-apify",
        description="CLI toolkit for Apify actors (Kensho portfolio)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    p_list = subparsers.add_parser("list", help="List all actors")
    p_list.add_argument("--category", help="Filter by category keyword")
    p_list.add_argument("--search", help="Filter by search keyword")
    p_list.add_argument("--limit", type=int, help="Limit output count")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    # info
    p_info = subparsers.add_parser("info", help="Show actor details")
    p_info.add_argument("id", help="Actor ID or name")
    p_info.add_argument("--json", action="store_true", help="Output as JSON")

    # run
    p_run = subparsers.add_parser("run", help="Trigger a test run")
    p_run.add_argument("id", help="Actor ID")
    p_run.add_argument("--timeout", type=int, help="Timeout in seconds")

    # stats
    p_stats = subparsers.add_parser("stats", help="Show actor statistics")
    p_stats.add_argument("id", help="Actor ID")
    p_stats.add_argument("--json", action="store_true", help="Output as JSON")

    # search
    p_search = subparsers.add_parser("search", help="Search actors")
    p_search.add_argument("keyword", help="Search keyword")
    p_search.add_argument("--json", action="store_true", help="Output as JSON")

    # seed
    p_seed = subparsers.add_parser("seed", help="Generate sample input data")
    p_seed.add_argument("--output", "-o", default=".", help="Output directory")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Fetch fresh actor data from API")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "list": cmd_list,
        "info": cmd_info,
        "run": cmd_run,
        "stats": cmd_stats,
        "search": cmd_search,
        "seed": cmd_seed,
        "fetch": cmd_fetch,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
