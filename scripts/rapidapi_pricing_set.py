#!/usr/bin/env python3
"""RapidAPI 有料プラン価格設定（Monetize・3-tier）— v17-B / 2026-09-05.

背景（t_868caac2 / t_698fc46c v14-A / t_bcd0e525 v17-B の経緯）:
- `createApiSubscription`（API-direct subscription作成）は recaptcha トークン不足で自動化不能。
- しかしプラン構成の読み書きは **2026-08-11 に JP/ES/PT 3言語版で完全自動化実証済み**:
    - 読み取り: `billingPlanVersions(where: {apiId})` → BASIC/PRO プラン・単価・クォータ
    - 書き込み: `updateBillingPlanExtended`（既存プラン価格更新）/ `createBillingPlan`（新規プラン作成）
- 本スクリプトはこの実証済み経路（CDP不要）で、対象APIに **3-tier 有料価格** を設定する:
      Basic  = $0.001/コール
      Pro    = $0.005/コール
      Ultra  = $0.01/コール
  冪等（すでに対象単価ならスキップ）。ULTRA が存在しなければ createBillingPlan で作成。

認証: `/mnt/d/Project2/goo-net-car-scraper/rapidapi_auth.json` の
cookie + csrf-token + x-entity-id（再利用する既存クレデンシャル。RapidAPI GraphQLは
このcookie経路のみ。consumer向け X-RapidAPI-Key は料金設定APIでは使えないため使用しない）。

対象API（タスク指定の2本）:
- japan-offmall-cn : api_3697e05e-3115-47c5-85df-f6edadbdc8ca  (PRIVATE)
- japan-camera     : api_7d2dcc27-829d-4add-88b9-5c1708447f85

使い方:
  python3 scripts/rapidapi_pricing_set.py --status
      全対象APIの各 tier 単価を表示（読み取り専用）
  python3 scripts/rapidapi_pricing_set.py --status --api japan-camera
      特定APIのみ
  python3 scripts/rapidapi_pricing_set.py --dry-run
      全 tier のペイロードを構築して出力（書き込みなし）
  python3 scripts/rapidapi_pricing_set.py --set-tiers
      対象2APIの 3-tier 価格を設定（Basic=0.001 / Pro=0.005 / Ultra=0.01）。冪等
  python3 scripts/rapidapi_pricing_set.py --set-tiers --api japan-offmall-cn
      特定APIのみ
  python3 scripts/rapidapi_pricing_set.py --set-price 0.005 --tier PRO
      単一 tier の単価を上書き（--tier 省略時は全 tier を同額に）
  python3 scripts/rapidapi_pricing_set.py --json
      JSON形式で出力（cron判定用）
  python3 scripts/rapidapi_pricing_set.py --retire-free-tier
      free 500K/旧 ACTIVE 版の退役を dry-run（削除せず分類のみ）
  python3 scripts/rapidapi_pricing_set.py --retire-free-tier --apply
      純 free プランを deleteBillingPlans で削除実行（有料 current 併存プランは安全のため対象外）
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

import requests

RAPIDAPI_AUTH = "/mnt/d/Project2/goo-net-car-scraper/rapidapi_auth.json"
GATEWAY = "https://rapidapi.com/gateway/graphql"

# タスク対象: goo-net JP＋Japanese OffMall Chinese と Japanese Camera
# (t_60f5b5de v11-A: goo-net JP = Japan Used Car Price Stats API に有料プラン導入)
TARGET_APIS = {
    "japan-used-car": {
        "api_id": "api_e093340e-c784-4cc9-9d70-7cf80404b9ed",
        "display": "Japan Used Car Price Stats API (goo-net JP)",
    },
    "japan-offmall-cn": {
        "api_id": "api_3697e05e-3115-47c5-85df-f6edadbdc8ca",
        "display": "Japan OffMall Used Goods Price Stats API (Chinese)",
    },
    "japan-camera": {
        "api_id": "api_7d2dcc27-829d-4add-88b9-5c1708447f85",
        "display": "Japan Camera & Lens Resale Price Research API",
    },
}

# 3-tier 有料価格（USD/コール）— v17-B タスク指定
TIER_PRICES = {
    "BASIC": 0.001,
    "PRO": 0.005,
    "ULTRA": 0.01,
}
DEFAULT_PRICE = 0.001  # 後方互換: --set-price で tier 未指定の既定


def _load_auth() -> dict:
    """rapidapi_auth.json を読み込み、Cookie dict と headers を返す."""
    if not os.path.exists(RAPIDAPI_AUTH):
        raise FileNotFoundError(f"RapidAPI auth file not found: {RAPIDAPI_AUTH}")
    with open(RAPIDAPI_AUTH, encoding="utf-8") as f:
        auth = json.load(f)
    cookies: dict[str, str] = {}
    if isinstance(auth.get("cookies"), str):
        for part in auth["cookies"].split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k] = v
    return {
        "cookies": cookies,
        "headers": {
            "content-type": "application/json",
            "csrf-token": auth.get("csrf_token", ""),
            "origin": "https://rapidapi.com",
            "rapid-client": "provider-dashboard-service",
            "referer": "https://rapidapi.com/_studio/",
            "x-entity-id": auth.get("entity_id", ""),
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
        },
        "entity_id": auth.get("entity_id", ""),
        "provider_name": auth.get("provider_name", "ino"),
    }


def _gql(auth: dict, query: str, variables: dict | None = None) -> dict:
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(GATEWAY, headers=auth["headers"], cookies=auth["cookies"], json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"GraphQL HTTP {resp.status_code}: {resp.text[:500]}")
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"GraphQL errors: {json.dumps(body['errors'], ensure_ascii=False)[:800]}")
    return body


def fetch_api_info(auth: dict, api_id: str) -> dict:
    """対象APIの currentVersion(id/name)/visibility を取得."""
    query = """
    query GetApi($where: ApiWhereInput) {
      apis(where: $where) {
        nodes {
          id
          name
          visibility
          currentVersion { id name }
        }
      }
    }
    """
    variables = {"where": {"id": [api_id], "ownerId": [auth["entity_id"]]}}
    body = _gql(auth, query, variables)
    nodes = (body.get("data") or {}).get("apis", {}).get("nodes") or []
    if not nodes:
        raise RuntimeError(f"API not found: {api_id}")
    return nodes[0]


def fetch_plan_versions(auth: dict, api_id: str) -> list[dict]:
    """billingPlanVersions を取得（全 tier の単価・クォータ・item/limit情報）."""
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
        }
      }
    }
    """
    variables = {"where": {"apiId": api_id}}
    body = _gql(auth, query, variables)
    nodes = (body.get("data") or {}).get("billingPlanVersions", {}).get("nodes") or []
    out = []
    for n in nodes:
        limits = []
        for bl in n.get("billinglimits", []) or []:
            item = bl.get("billingitem") or {}
            limits.append({
                "limit_id": bl.get("id"),
                "amount": bl.get("amount"),
                "limitType": bl.get("limitType"),
                "overageprice": bl.get("overageprice"),
                "period": bl.get("period"),
                "unlimited": bl.get("unlimited"),
                "item_id": item.get("id"),
                "item_name": item.get("name"),
            })
        bp = n.get("billingPlan") or {}
        out.append({
            "plan_id": bp.get("id"),
            "plan_name": (bp.get("name") or "").upper(),
            "version_id": n.get("id"),
            "version_name": n.get("name"),
            "price": n.get("price"),
            "period": n.get("period"),
            "status": n.get("status"),
            "current": bool(n.get("current")),
            "limits": limits,
        })
    return out


def per_call_price(version: dict) -> float | None:
    """計画バージョンの1コール単価 = billinglimit.overageprice / perusageprice の実体."""
    for lim in version.get("limits", []):
        ov = lim.get("overageprice")
        if ov is not None and float(ov) != 0:
            return float(ov)
    return None


def pick_plan_version(versions: list[dict], tier_name: str) -> dict | None:
    """指定 tier (BASIC/PRO/ULTRA) の ACTIVE バージョンを返す."""
    for v in versions:
        if v.get("plan_name") == tier_name.upper() and v.get("status") == "ACTIVE":
            return v
    return None


def fetch_billing_item_id(auth: dict, api_id: str) -> str:
    """billingItems クエリで Requests アイテムIDを取得（ULTRA 新規作成用）."""
    query = """
    query BillingItems($where: BillingItemsWhereInput!) {
      billingItems(where: $where) { nodes { id name } }
    }
    """
    variables = {"where": {"apiId": api_id}}
    body = _gql(auth, query, variables)
    items = (body.get("data") or {}).get("billingItems", {}).get("nodes") or []
    if not items:
        raise RuntimeError(f"billingItems not found for {api_id}")
    return items[0]["id"]


def _build_plan_input(auth: dict, api_info: dict, item_id: str, tier_name: str, price: float) -> dict:
    """createBillingPlan / updateBillingPlanExtended 共通の入力オブジェクト本体."""
    return {
        "api": api_info["id"],
        "apiName": api_info["name"],
        "apiVersion": api_info["currentVersion"]["id"],
        "apiVersionName": api_info["currentVersion"]["name"],
        "providerName": auth["provider_name"],
        "isStudent": False,
        "isPrivatePlan": False,
        "legalAccountId": "",
        "legalDocumentId": "",
        "name": tier_name.upper(),
        "targetGroup": "",
        "billingLimits": [
            {
                "amount": 0,
                "item": item_id,
                "limitType": "soft",
                "overagePrice": price,
                "period": "MONTHLY",
                "perusagePrice": price,
                "unlimited": False,
            }
        ],
        "enableBillingFeatures": [],
        "price": 0,
        "currency": None,
        "type": "PERUSE",
        "rateLimit": None,
    }


def create_plan(auth: dict, api_info: dict, item_id: str, tier_name: str, price: float) -> str | None:
    """ULTRA などの未存在プランを createBillingPlan で作成し、返り ID を返す."""
    mutation = """
    mutation C($billingPlan: BillingPlanCreateInput!) {
      createBillingPlan(billingPlan: $billingPlan) { id }
    }
    """
    variables = {"billingPlan": _build_plan_input(auth, api_info, item_id, tier_name, price)}
    body = _gql(auth, mutation, variables)
    return ((body.get("data") or {}).get("createBillingPlan") or {}).get("id")


def update_plan(
    auth: dict, api_info: dict, plan_version: dict, item_id: str, tier_name: str, price: float
) -> str | None:
    """既存プランを updateBillingPlanExtended で単価更新し、返り ID を返す."""
    payload = _build_plan_input(auth, api_info, item_id, tier_name, price)
    payload["billingPlanId"] = plan_version["plan_id"]
    mutation = """
    mutation U($billingPlan: BillingPlanExtendedUpdateInput!) {
      updateBillingPlanExtended(billingPlan: $billingPlan) { id }
    }
    """
    variables = {"billingPlan": payload}
    body = _gql(auth, mutation, variables)
    return ((body.get("data") or {}).get("updateBillingPlanExtended") or {}).get("id")


def ensure_tier(
    auth: dict, api_key: str, info: dict, versions: list[dict], tier_name: str, price: float, dry_run: bool
) -> dict:
    """1つの tier を対象単価に揃える（冪等）。return: 状態 dict."""
    tier_name = tier_name.upper()
    item_id = fetch_billing_item_id(auth, info["id"])
    # 同一プラン名の全 ACTIVE バージョンを収集（update は新バージョンを作るため複数あり得る）
    tier_versions = [v for v in versions if v.get("plan_name") == tier_name and v.get("status") == "ACTIVE"]
    # 対象単価と一致するバージョンがあれば冪等でスキップ
    for v in tier_versions:
        p = per_call_price(v)
        if p is not None and abs(p - price) < 1e-12:
            return {
                "tier": tier_name,
                "plan_id": v["plan_id"],
                "version_id": v["version_id"],
                "current_price": p,
                "target_price": price,
                "status": "unchanged",
                "message": "すでに対象単価のバージョンがあります（スキップ）.",
            }
    existing = pick_plan_version(versions, tier_name)
    current = per_call_price(existing) if existing else None

    if existing:
        if dry_run:
            return {
                "tier": tier_name,
                "plan_id": existing["plan_id"],
                "version_id": existing["version_id"],
                "current_price": current,
                "target_price": price,
                "status": "dry-run",
                "action": "update",
                "message": f"単価 {current} → {price} にするペイロード構築（未実行）.",
            }
        updated = update_plan(auth, info, existing, item_id, tier_name, price)
        return {
            "tier": tier_name,
            "plan_id": existing["plan_id"],
            "updated_id": updated,
            "current_price": current,
            "target_price": price,
            "status": "changed",
            "action": "update",
            "message": f"単価 {current} → {price} に更新.",
        }
    # 存在しない tier → 新規作成
    if dry_run:
        return {
            "tier": tier_name,
            "current_price": None,
            "target_price": price,
            "status": "dry-run",
            "action": "create",
            "message": f"新規プラン {tier_name} (${price}/call) 作成ペイロード構築（未実行）.",
        }
    try:
        created = create_plan(auth, info, item_id, tier_name, price)
        return {
            "tier": tier_name,
            "created_plan_id": created,
            "current_price": None,
            "target_price": price,
            "status": "created",
            "action": "create",
            "message": f"新規プラン {tier_name} (${price}/call) を作成.",
        }
    except RuntimeError as e:
        return {
            "tier": tier_name,
            "current_price": None,
            "target_price": price,
            "status": "error",
            "action": "create",
            "error": str(e),
        }


def set_tiers(
    auth: dict, api_key: str, prices: dict | None, single_price: float | None, only_tier: str | None, dry_run: bool
) -> dict:
    """対象APIに 3-tier 価格を設定。prices が None なら単一価格を全 tier に."""
    api = TARGET_APIS[api_key]
    api_id = api["api_id"]
    result: dict = {"api_id": api_id, "api_key": api_key, "api_name": api["display"]}
    prices = (
        prices
        if prices is not None
        else {
            t: (single_price if only_tier is None or t == only_tier.upper() else (TIER_PRICES.get(t, single_price)))
            for t in TIER_PRICES
        }
    )
    try:
        info = fetch_api_info(auth, api_id)
        result["api_name"] = info["name"]
        result["visibility"] = info.get("visibility")
        versions = fetch_plan_versions(auth, api_id)
    except RuntimeError as e:
        return {**result, "status": "error", "error": str(e)}

    tiers = [t for t in TIER_PRICES if not only_tier or t == only_tier.upper()]
    tier_results = []
    for t in tiers:
        try:
            tier_results.append(ensure_tier(auth, api_key, info, versions, t, prices[t], dry_run))
        except RuntimeError as e:
            tier_results.append({"tier": t, "status": "error", "error": str(e)})
    result["tiers"] = tier_results
    result["status"] = "error" if any(r["status"] == "error" for r in tier_results) else "ok"
    return result


def run_status(auth: dict, only: str | None) -> list[dict]:
    out = []
    for key, api in TARGET_APIS.items():
        if only and key != only:
            continue
        info = fetch_api_info(auth, api["api_id"])
        versions = fetch_plan_versions(auth, api["api_id"])
        tiers = []
        for t in TIER_PRICES:
            # 全 ACTIVE バージョン（consumer=current と orphan に区別が必要）
            tvers = [v for v in versions if v.get("plan_name") == t and v.get("status") == "ACTIVE"]
            if not tvers:
                continue
            # 消費者向け = current=True を優先。無ければ残骸(orphan)。
            consumer_vers = [v for v in tvers if v.get("current")]
            shown = consumer_vers or tvers
            ver = next(
                (
                    v
                    for v in shown
                    if per_call_price(v) is not None and abs((per_call_price(v) or 0.0) - TIER_PRICES[t]) < 1e-12
                ),
                shown[0],
            )
            tiers.append({
                "tier": t,
                "plan_id": ver["plan_id"],
                "version_id": ver["version_id"],
                "status": ver["status"],
                "current": ver.get("current"),
                "period": ver["period"],
                "per_call_price_usd": per_call_price(ver),
                "orphan_other_versions": len(tvers) - len(consumer_vers),
            })
        out.append({
            "api_key": key,
            "api_id": api["api_id"],
            "api_name": info["name"],
            "visibility": info.get("visibility"),
            "tiers": tiers,
        })
    return out


# ---------------------------------------------------------------------------
# free 500K tier 退役（t_60f5b5de v11-A: full PAID化の残務）
# ---------------------------------------------------------------------------


def _is_free_500k(limits: list[dict]) -> bool:
    """billinglimits が『月50万リクエスト無料 MONTHLY』か判定."""
    for bl in limits:
        if bl.get("period") == "MONTHLY" and (bl.get("amount") or 0) >= 500000 and not bl.get("overageprice"):
            return True
    return False


def fetch_plan_versions_full(auth: dict, api_id: str) -> list[dict]:
    """billingPlanVersions を購読者数・free500K判定付きで取得."""
    query = """
    query BillingPlans($where: BillingPlanVersionWhereInput) {
      billingPlanVersions(where: $where) {
        nodes {
          id name price period status current
          billingPlan { id name }
          billinglimits { id amount overageprice period limitType billingitem { id name } }
          subscriptions { id }
        }
      }
    }
    """
    body = _gql(auth, query, {"where": {"apiId": api_id}})
    nodes = (body.get("data") or {}).get("billingPlanVersions", {}).get("nodes") or []
    out: list[dict] = []
    for n in nodes:
        limits = []
        for bl in n.get("billinglimits", []) or []:
            limits.append({
                "limit_id": bl.get("id"),
                "amount": bl.get("amount"),
                "overageprice": bl.get("overageprice"),
                "period": bl.get("period"),
            })
        bp = n.get("billingPlan") or {}
        subs = n.get("subscriptions") or []
        out.append({
            "plan_id": bp.get("id"),
            "plan_name": (bp.get("name") or "").upper(),
            "version_id": n.get("id"),
            "version_name": n.get("name"),
            "price": n.get("price"),
            "period": n.get("period"),
            "status": n.get("status"),
            "current": bool(n.get("current")),
            "free500k": _is_free_500k(limits),
            "overageprice": next((bl["overageprice"] for bl in limits if bl["overageprice"]), None),
            "subscribers": len(subs),
        })
    return out


def retire_free_tier(auth: dict, api_key: str, apply: bool) -> dict:
    """free 500K / 旧 ACTIVE 版の退役を試行（安全・冪等・プラン併存保護あり）.

    deleteBillingPlans は **プラン単位**（billingplan_xxx）の削除で、同一プラン内の
    free 版と有料 current 版を同時削除してしまう。そこで「有料 current 版を保持する
    プラン」はプラン削除せず Studio UI（version 単位退避）が必要と分類する。
    有料 current が存在しない純 free プランのみ API 削除を実施する。
    """
    api = TARGET_APIS[api_key]
    api_id = api["api_id"]
    result: dict = {"api_id": api_id, "api_key": api_key}
    try:
        info = fetch_api_info(auth, api_id)
        result["api_name"] = info["name"]
        versions = fetch_plan_versions_full(auth, api_id)
    except RuntimeError as e:
        return {**result, "status": "error", "error": str(e)}

    buckets: dict[str, list[dict]] = {}
    for v in versions:
        buckets.setdefault(v["plan_id"], []).append(v)

    mutate = "mutation D($ids: [ID!]!){ deleteBillingPlans(ids:$ids) }"
    plans_out: list[dict] = []
    for plan_id, vers in buckets.items():
        pname = vers[0]["plan_name"]
        current_active = [v for v in vers if v.get("status") == "ACTIVE" and v.get("current")]
        retire_candidates = [v for v in vers if v.get("status") == "ACTIVE" and not v.get("current")]
        deletable = len(current_active) == 0 and len(retire_candidates) > 0
        entry = {
            "plan_id": plan_id,
            "plan_name": pname,
            "current_active_versions": [v["version_id"] for v in current_active],
            "retire_candidates": [
                {
                    "version_id": v["version_id"],
                    "free500k": v["free500k"],
                    "period": v["period"],
                    "per_call_usd": v["overageprice"],
                    "subscribers": v["subscribers"],
                }
                for v in retire_candidates
            ],
            "deletable_at_plan_level": deletable,
        }
        if deletable and apply:
            try:
                _gql(auth, mutate, {"ids": [plan_id]})
                entry["status"] = "deleted"
                entry["action"] = "deleteBillingPlans"
            except RuntimeError as e:
                entry["status"] = "error"
                entry["action"] = "deleteBillingPlans"
                entry["error"] = str(e)
        elif deletable:
            entry["status"] = "dry-run"
            entry["action"] = "deleteBillingPlans"
        elif current_active and retire_candidates:
            entry["status"] = "studio-ui-required"
            entry["action"] = "version-retire"
            # deleteBillingPlans はプラン単位のため、current 有料プランは UI で version 単位退避が必要
        else:
            entry["status"] = "none"
            entry["action"] = "noop"
        plans_out.append(entry)

    result["plans"] = plans_out
    result["has_ui_required"] = any(p["status"] == "studio-ui-required" for p in plans_out)
    result["status"] = "error" if any(p["status"] == "error" for p in plans_out) else "ok"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="RapidAPI 有料プラン価格設定 (Monetize・3-tier)")
    parser.add_argument("--status", action="store_true", help="各 tier 単価を表示（読み取り専用）")
    parser.add_argument("--dry-run", action="store_true", help="ペイロード構築のみ（書き込みなし）")
    parser.add_argument(
        "--set-tiers", action="store_true", help="3-tier 価格を設定（Basic=0.001 / Pro=0.005 / Ultra=0.01）"
    )
    parser.add_argument("--set-price", type=float, default=None, help="単一価格（--tier 未指定なら全 tier）USD/コール")
    parser.add_argument("--tier", choices=sorted(TIER_PRICES), help="対象 tier（--set-price 併用）")
    parser.add_argument("--api", choices=sorted(TARGET_APIS), help="対象API キー（省略=全対象）")
    parser.add_argument(
        "--retire-free-tier", action="store_true", help="free 500K/旧 ACTIVE 版の退役（--apply で実行）"
    )
    parser.add_argument("--apply", action="store_true", help="--retire-free-tier で実際に削除実行")
    parser.add_argument("--json", action="store_true", help="JSON形式で出力")
    args = parser.parse_args()

    auth = _load_auth()
    mode = args.set_tiers or args.set_price is not None or args.status or args.dry_run or args.retire_free_tier
    if not mode:
        parser.error(
            "--status / --dry-run / --set-tiers / --set-price / --retire-free-tier のいずれかを指定してください"
        )

    keys = [args.api] if args.api else list(TARGET_APIS)

    if args.retire_free_tier:
        results = [retire_free_tier(auth, k, args.apply) for k in keys]
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for r in results:
                print(f"### {r.get('api_key')} ({r.get('api_name')})  [{r.get('status')}]")
                for p in r.get("plans", []):
                    rc = p["retire_candidates"]
                    line = f"  plan={p['plan_name']} {p['status']:>18} action={p['action']} candidates={len(rc)}"
                    print(line)
                    if rc:
                        free = sum(1 for c in rc if c["free500k"])
                        print(
                            f"      free500k={free} 有料current={len(p['current_active_versions'])} "
                            f"うち購読者あり={sum(1 for c in rc if c['subscribers'])}"
                        )
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y%m%d_%H%M%S")
            report_path = Path("reports/revenue-proposals") / f"rapidapi-retire-free-tier-{now}.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"✓ 検証レコード: {report_path}", file=sys.stderr)
        return 0 if all(r.get("status") != "error" for r in results) else 1

    if args.status:
        rows = run_status(auth, args.api)
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            for r in rows:
                print(f"{r['api_key']:<16} {r['api_name'][:52]:<52} vis={r['visibility']}")
                if not r["tiers"]:
                    print("    (tier なし)")
                for t in r["tiers"]:
                    mark = "●current" if t.get("current") else "○orphan"
                    print(
                        f"    {t['tier']:<6} ${t['per_call_price_usd']}/call  "
                        f"{mark} orphan+{t.get('orphan_other_versions', 0)}  "
                        f"plan={t['plan_id'][:28]}... ver={t['version_id'][:28]}..."
                    )
        return 0

    if args.set_tiers or args.set_price is not None:
        dry_run = args.dry_run
        if args.set_price is not None:
            price = args.set_price
        else:
            price = None
        results = [
            set_tiers(
                auth, k, TIER_PRICES if args.set_tiers and args.set_price is None else None, price, args.tier, dry_run
            )
            for k in keys
        ]
    else:  # --dry-run only
        results = [set_tiers(auth, k, TIER_PRICES, None, None, True) for k in keys]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"### {r['api_key']} ({r['api_name']})")
            for t in r.get("tiers", []):
                if t.get("status") == "error":
                    print(f"  [ERR] {t['tier']}: {t.get('error')}", file=sys.stderr)
                else:
                    print(
                        f"  [{t['status']}] {t['tier']}: current=${t.get('current_price')} "
                        f"→ target=${t['target_price']} "
                        f"({t.get('action', '')}) {t.get('message', '')}"
                    )

        # 検証レコードを reports/ に書く
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y%m%d_%H%M%S")
        report_path = Path("reports/revenue-proposals") / f"rapidapi-pricing-set-{now}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓ 検証レコード: {report_path}", file=sys.stderr)

    return 0 if all(r["status"] != "error" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
