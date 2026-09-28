#!/usr/bin/env python3
"""Read back an Apify actor's public state to verify Store PPE listing."""
import json
import os
import sys
import urllib.request

TOKEN = os.environ.get("APIFY_TOKEN", "")
ACTOR_ID = sys.argv[1] if len(sys.argv) > 1 else "8cCUNDwmelphhoXFs"


def main() -> int:
    if not TOKEN:
        print("APIFY_TOKEN 未設定")
        return 1
    req = urllib.request.Request(
        f"https://api.apify.com/v2/actors/{ACTOR_ID}",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    a = data.get("data", {})
    print(f"name={a.get('name')} isPublic={a.get('isPublic')} "
          f"pricingModel={a.get('pricingModel')} datasetItemUsd={a.get('datasetItemUsd')} "
          f"startEventUsd={a.get('startEventUsd')} margin={a.get('margin')} "
          f"buildNumber={a.get('defaultBuildNumber')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())