#!/usr/bin/env python3
"""v26-1: RapidAPI FREEMIUM→有料化 — 候補5API に 3-tier 有料価格を設定する。

rapidapi_pricing_set.py の実証済み関数（冪等 create/update）を再利用して、
候補API の BASIC=$0.001 / PRO=$0.005 / ULTRA=$0.01（USD/コール）を設定する。
FREEMIUM（BASIC無料→有料化）のフラグ切替に相当。既に対象単価ならスキップ（冪等）。

認証: goo-net-car-scraper/rapidapi_auth.json（cookie 再利用）

使い方:
  python3 scripts/rapidapi_pricing_set_v26.py --status
  python3 scripts/rapidapi_pricing_set_v26.py --dry-run
  python3 scripts/rapidapi_pricing_set_v26.py --set-tiers
  python3 scripts/rapidapi_pricing_set_v26.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "/mnt/d/Project2/kensho/scripts")
import rapidapi_pricing_set as rps

TIER_PRICES = {"BASIC": 0.001, "PRO": 0.005, "ULTRA": 0.01}

TARGET_APIS = {
    "japan-kakaku": {"api_id": "api_45bf102f-6d1b-4fd5-9179-f164de167ffd", "display": "Japan Kakaku Price Stats API"},
    "japan-rent": {"api_id": "api_2e8e063d-f2a3-43de-9fe4-50d5eb16659a", "display": "Japan Rent Price Stats API"},
    "japan-watch": {
        "api_id": "api_cb7a9d01-e8db-4f0d-b91f-031899d5e7cc",
        "display": "Japan Used Watch Price Stats API",
    },
    "japan-luxury": {
        "api_id": "api_8941b445-afab-4f21-abbe-a58e96b21325",
        "display": "Japan Used Luxury Brand Price Stats API",
    },
    "japan-instrument": {
        "api_id": "api_8ccef00b-e8be-44b2-b4e4-3c96fdaf7481",
        "display": "Japan Used Musical Instrument Price Stats API",
    },
}


def status(auth):
    out = []
    for key, api in TARGET_APIS.items():
        info = rps.fetch_api_info(auth, api["api_id"])
        versions = rps.fetch_plan_versions(auth, api["api_id"])
        tiers = []
        for t in TIER_PRICES:
            tvers = [v for v in versions if v["plan_name"] == t and v.get("status") == "ACTIVE"]
            if not tvers:
                continue
            ver = next(
                (
                    v
                    for v in tvers
                    if rps.per_call_price(v) is not None
                    and abs((rps.per_call_price(v) or 0.0) - TIER_PRICES[t]) < 1e-12
                ),
                tvers[0],
            )
            tiers.append({"tier": t, "price": rps.per_call_price(ver), "status": ver["status"]})
        out.append({"api_key": key, "api_name": info["name"], "visibility": info.get("visibility"), "tiers": tiers})
    return out


def set_tiers(auth, dry_run):
    results = []
    for key in TARGET_APIS:
        api = TARGET_APIS[key]
        api_id = api["api_id"]
        print(f"### {key} ({api['display']})")
        info = rps.fetch_api_info(auth, api_id)
        versions = rps.fetch_plan_versions(auth, api_id)
        res = {
            "api_id": api_id,
            "api_key": key,
            "api_name": info["name"],
            "visibility": info.get("visibility"),
            "tiers": [],
        }
        for t in TIER_PRICES:
            try:
                tier_res = rps.ensure_tier(auth, key, info, versions, t, TIER_PRICES[t], dry_run)
            except RuntimeError as e:
                tier_res = {"tier": t, "status": "error", "error": str(e)}
            res["tiers"].append(tier_res)
            if tier_res.get("status") == "error":
                print(f"  [ERR] {t}: {tier_res.get('error')}")
            else:
                print(f"  {t:<6} {tier_res['status']}: {tier_res.get('message')}")
        res["status"] = "error" if any(x.get("status") == "error" for x in res["tiers"]) else "ok"
        results.append(res)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--set-tiers", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not (args.status or args.dry_run or args.set_tiers):
        parser.error("--status / --dry-run / --set-tiers のいずれか")

    auth = rps._load_auth()
    if args.status:
        rows = status(auth)
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            for r in rows:
                print(f"{r['api_key']:<16} {r['api_name'][:50]:<50} vis={r['visibility']}")
                for t in r["tiers"]:
                    print(f"    {t['tier']:<6} ${t['price']}/call")
        return 0

    if args.set_tiers or args.dry_run:
        set_tiers(auth, args.dry_run)
        return 0


if __name__ == "__main__":
    main()
