#!/usr/bin/env python3
"""Deploy mlit-japan-property-prices actor to Apify.

Steps:
  1. find-or-create actor "mlit-japan-property-prices"
  2. upload version 0.1 as SOURCE_FILES
  3. trigger build and wait for SUCCEEDED
  4. set Pay-Per-Event pricing
  5. publish (isPublic: true)
  6. verify and print summary

Usage:
    python3 scripts/deploy_mlit_actor.py [--no-publish] [--price 0.005]
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.apify.com/v2"
ACTOR_DIR = Path("/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_f54d4ff6")
ACTOR_NAME = "mlit-japan-property-prices"
# Pre-existing actor ID (from earlier deployment attempt)
ACTOR_ID = "ykFU6apmNgzFXgvkO"
VERSION_NUMBER = "0.3"
CATEGORY_CANDIDATES = [
    ["DATA", "JAPAN", "REAL_ESTATE"],
    ["DATA", "JAPAN"],
    ["DATA"],
]
SKIP_PARTS = {"__pycache__", "tests", ".pytest_cache", "storage"}
SKIP_SUFFIXES = {".pyc"}
SKIP_NAMES = {".coverage"}


def resolve_token() -> str:
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
    if token:
        return token.strip()
    env_file = Path("/mnt/d/Project2/kensho/.env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(("APIFY_TOKEN_DEFAULT=", "APIFY_TOKEN=")):
                return line.split("=", 1)[1].strip().strip('"')
    sys.exit("ERROR: no Apify token")


TOKEN = resolve_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}


def request(path: str, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        return {"_http_error": exc.code, "body": body_text[:500]}


def find_or_create_actor(name: str) -> str | None:
    """Find existing actor by name - actor already exists with known ID."""
    # Actor was pre-created; use known ID
    print(f"Using pre-existing actor: {ACTOR_ID}")
    return ACTOR_ID


def upload_version(actor_id: str) -> str | None:
    """Upload source files as version 0.1."""
    source_files = []
    for f in ACTOR_DIR.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            if any(skip in f.parts for skip in SKIP_PARTS):
                continue
            if f.suffix in SKIP_SUFFIXES:
                continue
            if f.name in SKIP_NAMES:
                continue
            content = f.read_bytes()
            source_files.append({
                "name": str(f.relative_to(ACTOR_DIR)),
                "content": base64.b64encode(content).decode(),
                "format": "BASE64",
            })
    
    print(f"Uploading {len(source_files)} source files...")
    payload = {
        "versionNumber": VERSION_NUMBER,
        "sourceType": "SOURCE_FILES",
        "sourceFiles": source_files,
        "buildTag": "latest",
    }
    r = request(f"/acts/{actor_id}/versions", payload)
    if "_http_error" in r:
        print(f"Version upload failed: {r}")
        sys.exit(1)
    version_id = r.get("data", {}).get("id") or r.get("id")
    print(f"Version uploaded: {version_id}")
    return version_id


def build_and_wait(actor_id: str, version_number: str) -> dict:
    """Trigger build and wait for completion."""
    print("Triggering build...")
    r = request(f"/acts/{actor_id}/builds?version={version_number}&useCache=0")
    if "_http_error" in r:
        print(f"Build trigger failed: {r}")
        sys.exit(1)
    build_id = r.get("data", {}).get("id")
    print(f"Build started: {build_id}")
    
    # Wait for completion
    for i in range(120):
        time.sleep(5)
        r = request(f"/actor-builds/{build_id}")
        if "_http_error" not in r:
            status = r.get("data", {}).get("status", "")
            print(f"  Build status: {status} ({i+1}/120)")
            if status in ("SUCCEEDED", "FAILED", "ABORTED"):
                if status == "SUCCEEDED":
                    print("Build succeeded!")
                    return r.get("data", {})
                else:
                    print(f"Build failed: {r.get('data', {}).get('statusMessage', 'Unknown')}")
                    sys.exit(1)
    
    print("Build timeout")
    sys.exit(1)


def set_pricing(actor_id: str, price_per_event: float):
    """Set PPE pricing."""
    now = dt.datetime.utcnow().isoformat() + "Z"
    pricing = {
        "pricingInfos": [
            {
                "eventType": "DEFAULT_DATASET_ITEM",
                "amount": price_per_event,
                "currency": "USD",
                "createdAt": now,
                "startedAt": now,
            }
        ]
    }
    r = request(f"/acts/{actor_id}", pricing, method="PUT")
    if "_http_error" in r:
        print(f"Pricing set failed: {r}")
    else:
        print(f"Pricing set: ${price_per_event}/record")


def publish_actor(actor_id: str):
    """Publish actor to Store."""
    payload = {
        "isPublic": True,
        "categories": ["DATA", "JAPAN", "REAL_ESTATE"],
        "title": "Japan Real Estate Transaction Prices API — MLIT Data (47 Prefectures)",
        "description": "Query transaction prices for Japanese real estate (47 prefectures, 2005-Q3 onwards) from the MLIT Reinfolib API. Returns structured JSON with price, area, location, building info, and zoning.",
    }
    r = request(f"/acts/{actor_id}", payload, method="PUT")
    if "_http_error" in r:
        print(f"Publish failed: {r}")
    else:
        print("Actor published to Store!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--price", type=float, default=0.005)
    args = parser.parse_args()
    
    print("=" * 60)
    print("Deploying MLIT Japan Property Prices Actor")
    print("=" * 60)
    
    # Step 1: Find or create actor
    actor_id = find_or_create_actor(ACTOR_NAME)
    if not actor_id:
        sys.exit("Failed to create actor")
    
    # Step 2: Upload version
    version_id = upload_version(actor_id)
    
    # Step 3: Build
    build_info = build_and_wait(actor_id, VERSION_NUMBER)
    
    # Step 4: Set pricing
    set_pricing(actor_id, args.price)
    
    # Step 5: Publish
    if not args.no_publish:
        publish_actor(actor_id)
    
    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"Actor ID: {actor_id}")
    print(f"Actor Name: {ACTOR_NAME}")
    print(f"Version: {VERSION_NUMBER}")
    print(f"Build: {build_info.get('id')}")
    print(f"Price: ${args.price}/record")
    print(f"Public: {'Yes' if not args.no_publish else 'No (dry run)'}")
    print(f"Store URL: https://apify.com/fruitful_quintessence/{ACTOR_NAME}")


if __name__ == "__main__":
    main()