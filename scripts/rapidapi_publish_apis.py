#!/usr/bin/env python3
"""RapidAPI PRIVATE→PUBLIC 公開スクリプト（t_0e8d78ab / 2026-09-06）。

既存の実証済み updateApi ミューテーション（goo-net-car-scraper/rapidapi_admin.py
cmd_publish と同形）で、対象APIの visibility を PUBLIC に変更する。
認証・GraphQLラッパーは rapidapi_pricing_set.py を再利用。

対象（task指定のPRIVATE候補3本）:
  - japan-offmall-cn : api_3697e05e-3115-47c5-85df-f6edadbdc8ca
  - japan-used-car   : api_e093340e-c784-4cc9-9d70-7cf80404b9ed
  - japan-camera     : api_7d2dcc27-829d-4add-88b9-5c1708447f85

安全性:
  - 公開前に各APIの visibility / tier をバックアップJSONに保存（risk節の
    「既存subscriberを失う」対策）。操作は visibility 変更のみで tier は不変。
  - --dry-run でペイロードのみ構築・検証（書き込みなし）。
  - 冪等: すでに PUBLUC の API はスキップ。

使い方:
  python3 scripts/rapidapi_publish_apis.py --status          # 現在値のみ（読み取り）
  python3 scripts/rapidapi_publish_apis.py --dry-run          # 公開計画（書き込みなし）
  python3 scripts/rapidapi_publish_apis.py --publish          # PUBLIC 公開を実行
  python3 scripts/rapidapi_publish_apis.py --publish --json   # 結果をJSONで出力
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rapidapi_pricing_set as rps  # noqa: E402

PUBLISH_TARGETS = {
    "japan-offmall-cn": {
        "api_id": "api_3697e05e-3115-47c5-85df-f6edadbdc8ca",
        "display": "Japan OffMall Used Goods Price Stats API (Chinese)",
    },
    "japan-used-car": {
        "api_id": "api_e093340e-c784-4cc9-9d70-7cf80404b9ed",
        "display": "Japan Used Car Price Stats API (goo-net JP)",
    },
    "japan-camera": {
        "api_id": "api_7d2dcc27-829d-4add-88b9-5c1708447f85",
        "display": "Japan Camera & Lens Resale Price Research API",
    },
}

OUT_DIR = Path("/mnt/d/Project2/kensho/data/rapidapi_publish")
BACKUP_PATH = OUT_DIR / "visibility_backup.json"
PLAN_PATH = OUT_DIR / "publish_plan.json"
RESULT_PATH = OUT_DIR / "publish_result.json"


def fetch_state(auth: dict) -> dict:
    """対象3本の now = {id, name, visibility, pricing, slugs[]}."""
    state = {}
    for key, api in PUBLISH_TARGETS.items():
        info = rps.fetch_api_info(auth, api["api_id"])
        # slug は list_apis のクエリで取得（公開URL用）
        slugs = _fetch_slugs(auth, api["api_id"])
        state[key] = {
            "api_id": api["api_id"],
            "name": info.get("name"),
            "visibility": info.get("visibility"),
            "pricing": info.get("pricing"),
            "slugs": slugs,
            "display": api["display"],
        }
    return state


def _fetch_slugs(auth: dict, api_id: str) -> list[str]:
    query = """
    query GetApi($where: ApiWhereInput) {
      apis(where: $where) { nodes { id slugifiedName } }
    }
    """
    variables = {"where": {"id": [api_id], "ownerId": [auth["entity_id"]]}}
    body = rps._gql(auth, query, variables)
    nodes = (body.get("data") or {}).get("apis", {}).get("nodes") or []
    return [n["slugifiedName"] for n in nodes if n.get("slugifiedName")]


def publish_one(auth: dict, api_id: str) -> dict:
    """updateApi で visibility=PUBLIC に変更。返り値: mutation結果 dict."""
    mutation = """
    mutation UpdateApi($api: ApiUpdateInput!) {
      updateApi(api: $api) {
        id
        visibility
      }
    }
    """
    variables = {"api": {"id": api_id, "visibility": "PUBLIC"}}
    body = rps._gql(auth, mutation, variables)
    return (body.get("data") or {}).get("updateApi") or {}


def build_plan(state: dict) -> dict:
    """PRIVATE でない（=まだ公開されていない）API を公開対象に選ぶ. 純粋関数（書き込みなし）."""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
    return {
        "created_at": now,
        "state_before": state,
        "to_publish": [
            {
                "api_key": k,
                "api_id": s["api_id"],
                "visibility_before": s["visibility"],
            }
            for k, s in state.items()
            if s["visibility"] != "PUBLIC"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RapidAPI PRIVATE→PUBLIC 公開")
    parser.add_argument("--status", action="store_true", help="現在の visibility のみ表示")
    parser.add_argument("--dry-run", action="store_true", help="ペイロード構築・公開対象リスト生成（書き込みなし）")
    parser.add_argument("--publish", action="store_true", help="PUBLIC 公開を実行")
    parser.add_argument("--json", action="store_true", help="結果をJSONで出力")
    args = parser.parse_args()

    if not (args.status or args.dry_run or args.publish):
        parser.error("--status / --dry-run / --publish のいずれか")

    auth = rps._load_auth()
    state = fetch_state(auth)

    if args.status:
        for key, s in state.items():
            vis = s["visibility"] or "None"
            pri = s["pricing"] or "None"
            print(f"{key:<18} vis={vis:<8} pricing={pri:<10} name={s['name']}")
        if args.json:
            print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    # 公開対象 = PRIVATE でないまだ見えていないもの（PUBLIC 以外を公開）
    plan = build_plan(state)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_PATH.write_text(
        json.dumps({"updated_at": plan["created_at"], "visibility_tier_backup": state}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if args.dry_run or not args.publish:
        PLAN_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        if args.json:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        else:
            print(f"公開対象 {len(plan['to_publish'])} 本:")
            for t in plan["to_publish"]:
                print(f"  {t['api_key']:<18} {t['api_id']}  vis={t['visibility_before']} -> PUBLIC")
            print(f"バックアップ: {BACKUP_PATH}")
            print(f"計画: {PLAN_PATH}")
            if not args.publish:
                print("（--dry-run: 書き込みなし。--publish で実行）")
        return 0

    # --publish 実行
    results = {}
    for t in plan["to_publish"]:
        try:
            res = publish_one(auth, t["api_id"])
            t["mutation"] = res
            t["result"] = "ok"
        except RuntimeError as e:
            t["result"] = "error"
            t["error"] = str(e)
        results[t["api_key"]] = t
    skipped = [k for k in state if state[k]["visibility"] == "PUBLIC"]

    # 公開後の再確認
    after = fetch_state(auth)
    final = {
        "created_at": plan["created_at"],
        "published": results,
        "skipped_already_public": skipped,
        "state_after": after,
    }
    RESULT_PATH.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps(final, indent=2, ensure_ascii=False))
    else:
        for key, t in results.items():
            mark = "OK" if t.get("result") == "ok" else f"ERR {t.get('error')}"
            after_vis = after[key]["visibility"] or "None"
            print(f"{key:<18} before={t['visibility_before'] or 'None':<8} -> {after_vis:<8} [{mark}]")
        if skipped:
            print(f"スキップ（既にPUBLIC）: {', '.join(skipped)}")
        print(f"結果: {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
