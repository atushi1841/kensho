#!/usr/bin/env python3
"""apify_seo_fill_gaps — remaining public actors missing SEO fields (egov-laws / jma-weather).

Individual GET confirmed description/seo fields already applied on 61/63 public
actors. Two public actors were incomplete (description present, seoDesc/cats
absent): japan-egov-laws and japan-jma-weather. This fills them via targeted PUT
using the proven category set (ECOMMERCE/AUTOMATION/DEVELOPER_TOOLS).

Usage: APIFY_TOKEN=apify_api_... python3 scripts/apify_seo_fill_gaps.py [--apply]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.apify.com/v2"
TOKEN = os.environ.get("APIFY_TOKEN", "").strip()

# Boundaries per Apify UpdateActorRequest schema.
CHAR_LIMITS = {
    "title": 63,
    "seoTitle": 60,
    "seoDescription": 160,
    "description": 300,
}

# Proven category set used across all 64 applied actors.
DEFAULT_CATEGORIES = ["ECOMMERCE", "AUTOMATION", "DEVELOPER_TOOLS"]

# Target payloads for the two remaining incomplete public actors.
TARGETS = {
    "japan-egov-laws": {
        "title": "Japan e-Gov Laws & Regulations Scraper",
        "seoTitle": "Japan Laws & Regulations Scraper — e-Gov",
        "seoDescription": (
            "Japan e-Gov legal texts scraper — Japanese laws, regulations "
            "and ordinances in JSON. Ideal for legal research and compliance "
            "datasets."
        ),
        "description": (
            "Japan e-Gov legal scraper. Extracts Japanese laws, regulations, "
            "cabinet orders and ministry ordinances with full text, effective "
            "dates and amendment history. JSON / CSV output via Apify dataset, "
            "pay-per-event. Ideal for legal research, compliance analysis, and "
            "Japanese regulatory AI training data."
        ),
        "categories": DEFAULT_CATEGORIES,
    },
    "japan-jma-weather": {
        "title": "Japan JMA Weather Data Scraper",
        "seoTitle": "Japan Weather Scraper — JMA Forecasts & Alerts",
        "seoDescription": (
            "Japan Meteorological Agency weather scraper — forecasts, "
            "observations, warnings. Current conditions and alerts in JSON for "
            "apps and monitoring."
        ),
        "description": (
            "Japan JMA (Meteorological Agency) weather scraper. Extracts "
            "current conditions, forecasts, wind, precipitation, temperature, "
            "and weather warnings/alerts for prefecture and city locations. "
            "JSON / CSV output via Apify dataset. Ideal for weather apps, "
            "monitoring dashboards, and data pipelines."
        ),
        "categories": DEFAULT_CATEGORIES,
    },
}


def fetch(url: str) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def put_actor(actor_id: str, payload: dict) -> tuple[int, dict]:
    url = f"{API_BASE}/acts/{actor_id}?token={TOKEN}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.getcode(), json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", errors="replace"))


def main() -> int:
    if not TOKEN:
        print("APIFY_TOKEN env required", file=sys.stderr)
        return 2
    apply = "--apply" in sys.argv
    listing = fetch(f"{API_BASE}/acts?my=true&token={TOKEN}&limit=100")
    items = listing.get("data", {}).get("items", [])
    by_name = {it["name"]: it["id"] for it in items}
    ok = 0
    fail = 0
    for name, payload in TARGETS.items():
        aid = by_name.get(name)
        if not aid:
            print(f"MISS {name}: not found")
            fail += 1
            continue
        for k, limit in CHAR_LIMITS.items():
            if len(payload[k]) > limit:
                print(f"  {name}.{k} len={len(payload[k])} too long")
                fail += 1
        before = fetch(f"{API_BASE}/acts/{aid}?token={TOKEN}").get("data", {})
        print(
            f"[{'APPLY' if apply else 'DRY'}] {name}: "
            f"before desc={len(before.get('description') or '')} "
            f"seoDesc={len(before.get('seoDescription') or '')} "
            f"cats={(before.get('categories') or [])}"
        )
        if apply:
            code, _body = put_actor(aid, payload)
            after = fetch(f"{API_BASE}/acts/{aid}?token={TOKEN}").get("data", {})
            print(
                f"  PUT http={code} -> after desc={len(after.get('description') or '')} "
                f"seoDesc={len(after.get('seoDescription') or '')} "
                f"seoTitle={len(after.get('seoTitle') or '')} "
                f"cats={(after.get('categories') or [])}"
            )
            ok += 1 if code == 200 else 0
            fail += 0 if code == 200 else 1
        else:
            print(
                f"  would set: desc(len {len(payload['description'])}) "
                f"seoTitle(len {len(payload['seoTitle'])}) "
                f"seoDesc(len {len(payload['seoDescription'])}) "
                f"cats={payload['categories']}"
            )
    print(f"\nok={ok} fail={fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
