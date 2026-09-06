#!/usr/bin/env python3
"""t_9c588435: camera JP 公開のための swap (冗長言語版をPRIVATE化して枠を空ける).

方針 (user decision 2026-09-06 19:29):
  上限制限20本のため、公開中21本の価値で最低位の冗長言語版をPRIVATE化して枠を空け、
  漏れの japan-used-camera-price-stats-api(JP) を PUBLIC にする。
  (本は20本上限のため、camera JP を公開すると PUBLIC が21本になる → 20本に収めるには
   冗長言語版を2本PRIVATE化する。)

決定根拠 (実データ):
  - data/revenue-daily.json (2026-09-06): RapidAPI 22本すべて FREEMIUM、
    revenue_estimate.rapidapi_monthly=0、全API paid subscriber=0 (free公認1名のみ)。
    → 全APIの収益は $0で同格。Apify Store アクターと重複する冗長言語版を最下位候補とする。
  - 冗長言語版PUBLICのうち最下位2本 = backing Apify アクターの usage が最小
    (6 runs, 直近) の camera-cn = api_daeb465c (japan-camera-market-cn-scraper) と
    camera-kr = api_9e1f6683 (japan-camera-market-kr-scraper)。
    直接の同family(JP stats)と重複、しかも日本版が漏れている family。→ 本命。

操作:
  1. mutation 前に全22本の visibility を data/rapidapi_publish/ にバックアップ (QA v38教訓)
  2. updateApi(id=api_daeb465c, visibility=PRIVATE)  # 最下位CNを閉鎖
  3. updateApi(id=api_9e1f6683, visibility=PRIVATE)  # 次点KRを閉鎖 → 枠を2つ空ける
  4. updateApi(id=api_e19e373c, visibility=PUBLIC)   # camera JP を公開 → PUBLIC 20本
  5. 再読取で camera=PUBLIC かつ PUBLIC総数=20 を検証

使い方: python3 scripts/rapidapi_swap_private_public.py --apply|--dry-run|--verify
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rapidapi_pricing_set as rps  # noqa: E402

TARGET_PUBLISH: dict[str, str] = {
    "api_id": "api_e19e373c-049e-462b-bd7c-c5acf9b65770",
    "display": "Japan Used Camera Price Stats API (JP original)",
}
TARGET_PRIVATIZE: list[dict[str, str]] = [
    {
        "api_id": "api_daeb465c-9094-4f76-8918-0b18e7b7915d",
        "display": "Japan Used Camera Price Stats API (Chinese) [lowest-value redundant]",
    },
    {
        "api_id": "api_9e1f6683-5736-4fee-a61e-8e248f21a449",
        "display": "Japan Used Camera Price Stats API (Korean) [2nd lowest, same family]",
    },
]

OUT_DIR = Path("/mnt/d/Project2/kensho/data/rapidapi_publish")
BACKUP_PATH = OUT_DIR / "visibility_swap_backup.json"
RESULT_PATH = OUT_DIR / "visibility_swap_result.json"

PUBLIC_CAP = 20


def list_all(auth: dict) -> dict[str, dict[str, Any]]:
    """entity 直下の全APIの id->name/visibility を取得."""
    q = """
    query GetApis($where: ApiWhereInput) {
      apis(where: $where) { nodes { id name visibility slugifiedName } }
    }
    """
    v = {"where": {"ownerId": [auth["entity_id"]]}}
    body = rps._gql(auth, q, v)
    nodes = (body.get("data") or {}).get("apis", {}).get("nodes") or []
    out: dict[str, dict[str, Any]] = {}
    for n in nodes:
        out[n["id"]] = {"name": n.get("name"), "visibility": n.get("visibility"), "slug": n.get("slugifiedName")}
    return out


def set_visibility(auth: dict, api_id: str, visibility: str) -> dict:
    mutation = """
    mutation UpdateApi($api: ApiUpdateInput!) {
      updateApi(api: $api) { id visibility name }
    }
    """
    v = {"api": {"id": api_id, "visibility": visibility}}
    body = rps._gql(auth, mutation, v)
    return (body.get("data") or {}).get("updateApi") or {}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()

    auth = rps._load_auth()

    if args.verify:
        state = list_all(auth)
        publics = [i for i, v in state.items() if v["visibility"] == "PUBLIC"]
        jp_vis = state.get(TARGET_PUBLISH["api_id"], {}).get("visibility")
        priv_vis = [state.get(t["api_id"], {}).get("visibility") for t in TARGET_PRIVATIZE]
        print(f"PUBLIC total = {len(publics)}  (expect {PUBLIC_CAP})")
        print(f"camera JP {TARGET_PUBLISH['api_id']} = {jp_vis}  (expect PUBLIC)")
        for t, vis in zip(TARGET_PRIVATIZE, priv_vis):
            print(f"privatized {t['api_id']} = {vis}  (expect PRIVATE)")
        ok = len(publics) == PUBLIC_CAP and jp_vis == "PUBLIC" and all(v == "PRIVATE" for v in priv_vis)
        print(f"VERIFY_PASS = {ok}")
        return 0

    # mutation 前バックアップ (QA v38教訓)
    state_before = list_all(auth)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_PATH.write_text(
        json.dumps({"created_at": now, "state_before": state_before}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    plan = {
        "rationale_short": "全RapidAPI収益$0(paid sub0)。冗長言語版のうちbacking Apify usage"
        "最小(camera-cn/kr 6 runs)2本をPRIVATE化して枠を空け、漏れのJP cameraを公開",
        "public_cap": PUBLIC_CAP,
        "steps": [
            {
                "op": f"updateApi {t['display']}",
                "api_id": t["api_id"],
                "visibility_before": state_before.get(t["api_id"], {}).get("visibility"),
                "visibility_after": "PRIVATE",
            }
            for t in TARGET_PRIVATIZE
        ]
        + [
            {
                "op": f"updateApi {TARGET_PUBLISH['display']}",
                "api_id": TARGET_PUBLISH["api_id"],
                "visibility_before": state_before.get(TARGET_PUBLISH["api_id"], {}).get("visibility"),
                "visibility_after": "PUBLIC",
            }
        ],
    }
    print("PLAN:")
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    print(f"Backup written: {BACKUP_PATH}")

    if args.dry_run or not args.apply:
        print("(dry-run: 書き込みなし。--apply で実行)")
        return 0

    results: dict[str, Any] = {}
    order: list[tuple[str, str, str]] = [(t["api_id"], "PRIVATE", t["display"]) for t in TARGET_PRIVATIZE] + [
        (TARGET_PUBLISH["api_id"], "PUBLIC", TARGET_PUBLISH["display"])
    ]
    for api_id, vis, disp in order:
        before = state_before.get(api_id, {}).get("visibility")
        try:
            res = set_visibility(auth, api_id, vis)
            results[api_id] = {"op": disp, "before": before, "mutation": res, "ok": True}
        except RuntimeError as e:
            results[api_id] = {"op": disp, "before": before, "ok": False, "error": str(e)}
        mark = (
            json.dumps(results[api_id].get("mutation"), ensure_ascii=False)
            if results[api_id]["ok"]
            else f"ERR {results[api_id]['error']}"
        )
        print(f"{disp:<52} vis {before} -> {vis}  {mark}")

    # 実行後再読取
    state_after = list_all(auth)
    publics = [i for i, v in state_after.items() if v["visibility"] == "PUBLIC"]
    final = {
        "created_at": now,
        "plan": plan,
        "results": results,
        "state_after_public_total": len(publics),
        "camera_jp_visibility": state_after.get(TARGET_PUBLISH["api_id"], {}).get("visibility"),
        "privatized_visibilities": {
            t["api_id"]: state_after.get(t["api_id"], {}).get("visibility") for t in TARGET_PRIVATIZE
        },
        "verify_pass": len(publics) == PUBLIC_CAP
        and state_after.get(TARGET_PUBLISH["api_id"], {}).get("visibility") == "PUBLIC"
        and all(state_after.get(t["api_id"], {}).get("visibility") == "PRIVATE" for t in TARGET_PRIVATIZE),
    }
    RESULT_PATH.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PUBLIC total after = {len(publics)}  (expect {PUBLIC_CAP})")
    print(f"camera JP visibility = {final['camera_jp_visibility']}")
    for t in TARGET_PRIVATIZE:
        print(f"privatized {t['api_id']} = {state_after.get(t['api_id'], {}).get('visibility')}")
    print(f"VERIFY_PASS = {final['verify_pass']}")
    print(f"result: {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
