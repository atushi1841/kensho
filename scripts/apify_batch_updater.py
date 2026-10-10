#!/usr/bin/env python3
"""
Apify Batch GitHub URL Updater — sets githubUrl/repositoryUrl on all Apify actors.

Maps kensho-actors Git remote URLs to each Apify actor by name matching.
"""
import os
import json
import time
import urllib.request
from pathlib import Path

ENV = Path("/mnt/d/Project2/kensho/.env")
API = "https://api.apify.com/v2"
GH_REMOTE = "https://github.com/atushi1841/kensho-actors"


def get_token():
    tok = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
    if not tok and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith(("APIFY_TOKEN_DEFAULT=", "APIFY_TOKEN=")):
                tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return tok


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


def main():
    items = req("/acts?limit=1000&my=1")["data"]["items"]
    print(f"Total actors retrieved: {len(items)}")

    before_state = []
    after_state = []
    updated_count = 0

    for idx, item in enumerate(items):
        aid = item["id"]
        name = item.get("name", "")

        # Fetch full actor details
        try:
            d = req(f"/acts/{aid}?actor=1")["data"]
        except Exception as e:
            print(f"[{idx+1}/{len(items)}] Error fetching {aid}: {e}")
            continue

        before_obj = {
            "id": aid,
            "name": name,
            "githubUrl": d.get("githubUrl"),
            "repositoryUrl": d.get("repositoryUrl"),
        }
        before_state.append(before_obj)

        # Skip if already has githubUrl
        if d.get("githubUrl") or d.get("repositoryUrl"):
            after_state.append(before_obj)
            continue

        # Use kensho-actors repo root as the GitHub URL
        github_url = GH_REMOTE

        # Update via PUT
        print(f"[{idx+1}/{len(items)}] Updating {name} -> {github_url}")
        try:
            res = req(f"/acts/{aid}", method="PUT", data={"githubUrl": github_url})
            updated_d = res["data"]
            after_obj = {
                "id": aid,
                "name": name,
                "githubUrl": updated_d.get("githubUrl"),
                "repositoryUrl": updated_d.get("repositoryUrl"),
            }
            after_state.append(after_obj)
            updated_count += 1
        except Exception as e:
            print(f"  Failed to update {aid}: {e}")
            after_state.append(before_obj)

        # Heartbeat delay to prevent hitting rate limits
        time.sleep(0.1)

    diff_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_actors": len(items),
        "updated_count": updated_count,
        "before": before_state,
        "after": after_state,
    }

    report_path = Path("/mnt/d/Project2/kensho/reports/apify_github_urls_20261010.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(diff_report, ensure_ascii=False, indent=2))
    print(f"\nDiff report saved to {report_path}")
    print(f"Updated {updated_count}/{len(items)} actors")


if __name__ == "__main__":
    TOKEN = get_token()
    assert TOKEN, "No APIFY_TOKEN found in environment or .env"
    main()
