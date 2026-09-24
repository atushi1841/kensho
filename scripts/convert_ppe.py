#!/usr/bin/env python3
"""Convert FREE public actors to PAY_PER_EVENT pricing"""

import json
import os
import urllib.request
import urllib.error
import sys
import copy
from datetime import datetime, timezone

TOKEN = os.environ.get('APIFY_TOKEN_DEFAULT') or open('.env').read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip()

BASE = "https://api.apify.com/v2"

def _request(path: str, body: object = None, method: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR: HTTP {e.code} at {path}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: network failure at {path}: {e.reason}")

def get(path: str) -> dict:
    return _request(path)

def put(path: str, body: object) -> dict:
    return _request(path, body=body, method="PUT")

def convert_to_ppe(actor_id: str, target_price: float, actor_name: str):
    print(f"Converting {actor_name} (ID: {actor_id}) to PAY_PER_EVENT with price ${target_price}")
    
    try:
        # Get actor details
        d = get(f"/acts/{actor_id}")
        actor = d["data"]
        
        # Check if already has PPE
        pis = actor.get("pricingInfos", [])
        if pis and any(pi.get("pricingModel") == "PAY_PER_EVENT" for pi in pis):
            print(f"  ⚠ Already has PAY_PER_EVENT pricing, skipping")
            return True
        
        # Determine if we need to create new pricing entry
        # For actors with no pricingInfos, create a new one
        # For actors with pricingInfos, add a new one as the latest
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Create new pricing record
        # Create new pricing record
        newrec = {
            "pricingModel": "PAY_PER_EVENT",
            "apifyMarginPercentage": 0.2,
            "createdAt": now,
            "startedAt": now,
            "pricingPerEvent": {
                "actorChargeEvents": {
                    "apify-default-dataset-item": {
                        "eventTitle": "result",
                        "eventDescription": "Single result in the default dataset.",
                        "eventPriceUsd": target_price,
                        "isOneTimeEvent": False,
                        "isPrimaryEvent": True
                    }
                }
            }
        }
        
        # Add to pricingInfos
        new_pis = pis + [newrec]
        
        # Update actor
        put(f"/acts/{actor_id}", {"pricingInfos": new_pis})
        print(f"  ✓ Updated {actor_id}")
        return True
        
    except Exception as e:
        print(f"  ✗ Error converting {actor_name}: {e}")
        return False

def main():
    # Target actors from the task
    target_actors = [
        ('pWhvh8aWz4i6OM1ST', 'japan-egov-laws', 0.002),
        ('rIZ3NSg5Ul34PgpYx', 'japan-corporate-numbers', 0.002),
        ('u2qsG1UfVHWsgl8Dg', 'world-bank-indicators', 0.003),
        ('pAxQ0lRyArudhK9Wx', 'eurostat-indicators', 0.004),
        ('BxstMzzxh8jq6UtfS', 'japan-jepx-mcp', 0.005),
    ]
    
    success_count = 0
    for actor_id, actor_name, price in target_actors:
        if convert_to_ppe(actor_id, price, actor_name):
            success_count += 1
    
    print(f"\nConversion complete: {success_count}/{len(target_actors)} actors converted")

if __name__ == "__main__":
    main()