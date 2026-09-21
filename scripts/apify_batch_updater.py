#!/usr/bin/env python3
"""
Apify Batch SEO & Metadata Updater for t_9e7b7456
"""
import os
import json
import time
import urllib.request
from pathlib import Path

ENV = Path("/mnt/d/Project2/kensho/.env")
API = "https://api.apify.com/v2"

def get_token():
    tok = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
    if not tok and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith(("APIFY_TOKEN_DEFAULT=", "APIFY_TOKEN=")):
                tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return tok

TOKEN = get_token()
assert TOKEN, "No APIFY_TOKEN found in environment or .env"

def req(path, method="GET", data=None):
    url = f"{API}{path}"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode("utf-8") if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())

def get_all_actors():
    lst = req("/acts?limit=1000&my=1")
    return lst["data"]["items"]

def main():
    items = get_all_actors()
    print(f"Total actors retrieved: {len(items)}")

    # Standard default pictureUrl to use for actors if they don't have one
    # Default public icon for Kensho / Data scrapers on GitHub/CDN
    DEFAULT_PICTURE_URL = "https://raw.githubusercontent.com/atushi1841/apify-actors-assets/main/kensho-default-icon.png"

    before_state = []
    after_state = []

    for idx, item in enumerate(items):
        aid = item["id"]
        # fetch full actor details
        try:
            d = req(f"/acts/{aid}?actor=1")["data"]
        except Exception as e:
            print(f"[{idx+1}/{len(items)}] Error fetching {aid}: {e}")
            continue

        before_obj = {
            "id": aid,
            "name": d.get("name"),
            "title": d.get("title"),
            "pictureUrl": d.get("pictureUrl"),
            "categories": d.get("categories"),
            "isPublic": d.get("isPublic")
        }
        before_state.append(before_obj)

        # Prepare updates
        updated = False
        payload = {}

        # 1. Custom Icon / pictureUrl
        current_pic = d.get("pictureUrl")
        if not current_pic:
            payload["pictureUrl"] = DEFAULT_PICTURE_URL
            updated = True

        # 2. Categorization
        current_cats = d.get("categories") or []
        if not current_cats:
            # Default categories if empty
            # Apify API expects categoryIds, not categories
            payload["categoryIds"] = ["DEVELOPER_TOOLS", "AUTOMATION", "ECOMMERCE"]
            updated = True

        if updated:
            print(f"[{idx+1}/{len(items)}] Updating {d.get('name')} ({aid})...")
            try:
                # Update actor via PUT /acts/{id}
                res = req(f"/acts/{aid}", method="PUT", data=payload)
                updated_d = res["data"]
                after_obj = {
                    "id": aid,
                    "name": updated_d.get("name"),
                    "title": updated_d.get("title"),
                    "pictureUrl": updated_d.get("pictureUrl"),
                    "categories": updated_d.get("categories"),
                    "isPublic": updated_d.get("isPublic")
                }
                after_state.append(after_obj)
            except Exception as e:
                print(f"Failed to update {aid}: {e}")
                after_state.append(before_obj)
        else:
            after_state.append(before_obj)

        # Heartbeat delay to prevent hitting rate limits
        time.sleep(0.1)

    diff_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_actors": len(items),
        "before": before_state,
        "after": after_state
    }

    report_path = Path("/mnt/d/Project2/kensho/reports/apify_seo_diff_2026-09-21.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(diff_report, ensure_ascii=False, indent=2))
    print(f"Diff report saved to {report_path}")

if __name__ == "__main__":
    main()
