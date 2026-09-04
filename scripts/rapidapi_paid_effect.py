#!/usr/bin/env python3
"""RapidAPI 有料プラン 2週間効果測定 — 読み取り専用（t_868caac2 / 2026-09-05).

経緯: t_868caac2（FREEMIUM→PAID テスト）は本体の価格設定を
t_bcd0e525(API-direct)/t_60f5b5de(CDP+UI) が実施。本スクリプトはタスクの
もう半分の目的「2週間で効果を測定する」を担う。

測定する内容（全て読み取り専用・mutationなし）:
  1. 各 API の tier(BASIC/PRO/ULTRA) ごとの ACTIVE バージョン一覧と実効単価
     （per_call_price = billinglimit.overageprice / perusageprice の実体）
  2. 各バージョンの購読者数（subscriptions）
  3. 有料subscriber数 / 無料(0円 or 月500K)subscriber数
  4. hygiene 警告: 同一 tier に複数 ACTIVE（単価競合）や、有料と無料バージョンが
     共存（無料逃げ込み）がある場合を検出

出力: data/rapidapi_paid_effect_state.json（日付キーで point 追加・直近N日保持）
      revenue-daily.json には kensho_revenue_collect.attach_rapidapi_paid_effect_keys が添付。

使い方:
  python3 scripts/rapidapi_paid_effect.py --dry-run  読み取りのみ・保存しない
  python3 scripts/rapidapi_paid_effect.py             読み取りして state に当日 point を追記
  python3 scripts/rapidapi_paid_effect.py --json     JSON で結果を出力
  python3 scripts/rapidapi_paid_effect.py --report   状態print + 検証レコードを reports に書く

認証: /mnt/d/Project2/goo-net-car-scraper/rapidapi_auth.json（既存クレデンシャル再利用）
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

# 既存の価格設定スクリプトの読み取りヘルパーを再利用（自身は何も書き換えない）
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rapidapi_pricing_set as rps  # noqa: E402

STATE_PATH = "/mnt/d/Project2/kensho/data/rapidapi_paid_effect_state.json"
REPORT_DIR = Path("/mnt/d/Project2/kensho/reports/revenue-proposals")
MAX_POINTS = 30  # 2週間測定 + 余裕

# 有料tier の判定: 実効単価が 0 より大きい場合を「有料」とする
# 無料逃げ込み: BASIC の月500K 無料バージョンが有料バージョンと同時に ACTIVE
FREE_MONTHLY_THRESHOLD = 500000


def fetch_versions_with_subs(auth: dict[str, Any], api_id: str) -> list[dict[str, Any]]:
    """billingPlanVersions を subscriptions 込みで取得（読み取り専用）. """
    query = """
    query BillingPlans($where: BillingPlanVersionWhereInput) {
      billingPlanVersions(where: $where) {
        nodes {
          id name price period status current
          billingPlan { id name }
          billinglimits {
            id amount limitType overageprice period unlimited currency
            billingitem { id name }
          }
          subscriptions { id }
        }
      }
    }
    """
    variables = {"where": {"apiId": api_id}}
    body = rps._gql(auth, query, variables)
    nodes = (body.get("data") or {}).get("billingPlanVersions", {}).get("nodes") or []
    out: list[dict[str, Any]] = []
    for n in nodes:
        limits = []
        for bl in n.get("billinglimits", []) or []:
            item = bl.get("billingitem") or {}
            limits.append({
                "amount": bl.get("amount"),
                "limitType": bl.get("limitType"),
                "overageprice": bl.get("overageprice"),
                "period": bl.get("period"),
                "unlimited": bl.get("unlimited"),
                "item_name": item.get("name"),
            })
        bp = n.get("billingPlan") or {}
        subs = n.get("subscriptions") or []
        out.append({
            "plan_id": bp.get("id"),
            "plan_name": (bp.get("name") or "").upper(),
            "version_id": n.get("id"),
            "version_name": n.get("name"),
            "price_field": n.get("price"),
            "period": n.get("period"),
            "status": n.get("status"),
            "current": bool(n.get("current")),
            "limits": limits,
            "subscribers": len(subs),
        })
    return out


def per_call_price(v: dict[str, Any]) -> float | None:
    """plan version の1コール実効単価（overageprice）。"""
    for lim in v.get("limits", []):
        ov = lim.get("overageprice")
        if ov is not None and float(ov) != 0:
            return float(ov)
    return None


def is_free_monthly(v: dict[str, Any]) -> bool:
    """月500K無料（FREEMIUM のデフォルト BASIC）バージョンか。"""
    if per_call_price(v) is not None:
        return False
    for lim in v.get("limits", []):
        if lim.get("limitType") in ("soft", "hard") and lim.get("period") == "MONTHLY":
            amt = lim.get("amount")
            if amt is not None and int(amt) >= FREE_MONTHLY_THRESHOLD:
                return True
    return False


def measure_api(auth: dict[str, Any], api_key: str, api_def: dict[str, Any]) -> dict[str, Any]:
    """1 API の有料プラン効果指標を測定（読み取り専用）。"""
    api_id = api_def["api_id"]
    info = rps.fetch_api_info(auth, api_id)
    versions = fetch_versions_with_subs(auth, api_id)

    # tier ごとにバージョンを分類:
    #   消費者向け(マーケットプレイスで表示される) = current=True の ACTIVE 版
    #   オーファン = ACTIVE だが current=False（DB残骸。購読者は選択不可）
    by_tier: dict[str, dict[str, Any]] = {}
    for v in versions:
        if v.get("status") != "ACTIVE":
            continue
        bucket = by_tier.setdefault(v["plan_name"], {"consumer": [], "orphan": []})
        bucket["consumer" if v.get("current") else "orphan"].append(v)

    tiers: dict[str, Any] = {}
    warnings: list[str] = []
    for tier_name, bucket in sorted(by_tier.items()):
        consumer = [{
            "version_id": v["version_id"],
            "period": v["period"],
            "per_call_price_usd": per_call_price(v),
            "free_monthly_500k": is_free_monthly(v),
            "subscribers": v["subscribers"],
        } for v in bucket["consumer"]]
        orphan = [{
            "version_id": v["version_id"],
            "period": v["period"],
            "per_call_price_usd": per_call_price(v),
            "free_monthly_500k": is_free_monthly(v),
            "subscribers": v["subscribers"],
        } for v in bucket["orphan"]]
        # 実効単価は消費者向け(現在)バージョンの有料最小値
        paid = [a for a in consumer if (a["per_call_price_usd"] or 0) > 0]
        effective_price = min((a["per_call_price_usd"] for a in paid), default=None)
        sub_count = sum(a["subscribers"] for a in consumer)
        tiers[tier_name] = {
            "consumer_versions": consumer,
            "consumer_versions_count": len(consumer),
            "orphan_versions_count": len(orphan),
            "effective_per_call_price_usd": effective_price,
            "subscribers": sub_count,
        }
        # hygiene: 消費者向け(current)に複数 → 単価競合（実質表示は1つだが安全側で警告）
        if len(consumer) > 1:
            warnings.append(
                f"{tier_name}: 消費者向けcurrent版が {len(consumer)} 個共存（単価競合 / 実効価格が曖昧）"
            )
        # 消費者向け(current)が本当に無料のまま(=FREEMIUM)なら警告
        if effective_price is None and consumer:
            warnings.append(f"{tier_name}: 消費者向けが無料のみ（PAID未設定）→ 収益 $0")
        # オーファンに購読者がいる場合のみ注意（マーケ表示はされないが潜在リスク）
        for a in orphan:
            if a["free_monthly_500k"] and a["subscribers"] > 0:
                warnings.append(f"{tier_name}: 無料オーファン版に既存購読者 {a['subscribers']}人（中途解約自由）")

    total_subs = sum(t["subscribers"] for t in tiers.values())
    paid_subs = sum(
        a["subscribers"]
        for t in tiers.values()
        for a in t.get("consumer_versions", [])
        if (a["per_call_price_usd"] or 0) > 0
    )
    free_subs = total_subs - paid_subs

    return {
        "api_key": api_key,
        "api_id": api_id,
        "api_name": info.get("name"),
        "visibility": info.get("visibility"),
        "tiers": tiers,
        "tier_effective_prices": {
            k: v["effective_per_call_price_usd"] for k, v in tiers.items()
        },
        "subscribers": {"total": total_subs, "paid": paid_subs, "free": free_subs},
        "warnings": warnings,
        "paid_plan_active": any(
            v["effective_per_call_price_usd"] is not None for v in tiers.values()
        ),
    }


def collect_all(auth: dict[str, Any]) -> list[dict[str, Any]]:
    # 対象 = 既存の価格設定済み(v17-B/v11-A) + v26-1 で有料化した5本
    targets = dict(rps.TARGET_APIS)
    for key, api in RAPIDAPI_V26_APIS.items():
        targets.setdefault(key, api)
    return [measure_api(auth, k, d) for k, d in targets.items()]


# v26-1 で有料化した5本（t_25a7704e）。paid_effect の測定・cron 添付対象に含める
RAPIDAPI_V26_APIS: dict[str, dict[str, Any]] = {
    "japan-kakaku": {"api_id": "api_45bf102f-6d1b-4fd5-9179-f164de167ffd", "display": "Japan Kakaku Price Stats API"},
    "japan-rent": {"api_id": "api_2e8e063d-f2a3-43de-9fe4-50d5eb16659a", "display": "Japan Rent Price Stats API"},
    "japan-watch": {"api_id": "api_cb7a9d01-e8db-4f0d-b91f-031899d5e7cc", "display": "Japan Used Watch Price Stats API"},
    "japan-luxury": {"api_id": "api_8941b445-afab-4f21-abbe-a58e96b21325", "display": "Japan Used Luxury Brand Price Stats API"},
    "japan-instrument": {"api_id": "api_8ccef00b-e8be-44b2-b4e4-3c96fdaf7481", "display": "Japan Used Musical Instrument Price Stats API"},
}


def load_state() -> dict[str, Any]:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                state = json.load(f)
            if isinstance(state, dict):
                return state
        except Exception:
            pass
    return {"points": {}}


def save_state(state: dict[str, Any]) -> None:
    Path(STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="RapidAPI 有料プラン効果測定（読み取り専用）")
    parser.add_argument("--dry-run", action="store_true", help="読み取りのみ・state保存しない")
    parser.add_argument("--json", action="store_true", help="JSON で結果を出力")
    parser.add_argument("--report", action="store_true", help="状態print + 検証レコードを reports に書く")
    args = parser.parse_args()

    auth = rps._load_auth()
    results = collect_all(auth)

    per_api = {r["api_key"]: {k: v for k, v in r.items() if k != "api_key"} for r in results}
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")
    point = {
        "point": "baseline" if args.dry_run else "measured",
        "point_date": today,
        "measured_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
        "per_api": per_api,
    }

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    # human print
    for r in results:
        print(f"### {r['api_key']} ({r['api_name']}) vis={r['visibility']}")
        for tier_name, t in r["tiers"].items():
            price = t["effective_per_call_price_usd"]
            pr = "FREE" if price is None else f"${price}/call"
            print(f"  {tier_name:<6} effective={pr:<12} subs={t['subscribers']} "
                  f"consumer={t['consumer_versions_count']} orphan={t['orphan_versions_count']}")
            for a in t["consumer_versions"]:
                tag = " [FREE月500K]" if a["free_monthly_500k"] else ""
                print(f"      ver={a['version_id'][:20]}... price={a['per_call_price_usd']} "
                      f"period={a['period']} subs={a['subscribers']}{tag}")
        s = r["subscribers"]
        print(f"  PAID subscribers: {s['paid']}  FREE: {s['free']}  total: {s['total']}")
        for w in r["warnings"]:
            print(f"  ⚠️ {w}")

    if args.report:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"rapidapi-paid-effect-{now}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓ 検証レコード: {report_path}", file=sys.stderr)

    if not args.dry_run:
        state = load_state()
        state.setdefault("points", {})[today] = point
        # 直近MAX_POINTS日分に切る
        dates = sorted(state["points"].keys())
        for d in dates[:-MAX_POINTS]:
            state["points"].pop(d, None)
        save_state(state)
        print(f"✓ state 更新: {STATE_PATH}（{len(state['points'])} points）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
