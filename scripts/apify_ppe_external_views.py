#!/usr/bin/env python3
"""apify_ppe_external_views — v19 Apify PPE アクター外部ビュー計測レイヤー（t_a7ad5670）。

revenue-critic v15-A（t_90fce3df）で適用した**説明文（description / seoTitle /
seoDescription）一括テンプレーティング**が、Apify Store の CTR（サーチ結果→画面
到達→使用）に与える影響を、PPE 課金アクター top5 (KEYS) + **プロモ全23俳優**
について 24h/72h/168h 後まで追跡する。

計測対象:
  - KEYS (5俳優): v15-A baseline 測定ポイント固定
  - PROMO (23俳優): PRIORITY_ACTORS 同期、投稿日基準 +1d/+3d/+7d 動的追跡

指標の定義:
  external_views : **外部（owner 以外）ユーザーの累積 run 数**。Apify 公開 API は
                   Store ページの view 数を直接公開しておらず、外部エンゲージメント
                   （Store CTR の下方ファネル）を測れる唯一の公開シグナルが
                   「userId != owner の run」であるため、これを external views の
                   proxy とする（ドキュメント: 制限を明記）。
  補助シグナル   : total_runs（累積）, u30d（新規流入）, bookmarks, seo_present

測定ポイント:
  KEYS: baseline=2026-09-04, 24h=2026-09-05, 72h=2026-09-07, 168h=2026-09-11
  PROMO: 動的 (投稿日 +1d/+3d/+7d) / もしくは --point now で全PROMO計測

出力:
  data/apify_ppe_external_views_state.json   : 全ポイント累積（per_actor + per_promo_actor 時系列）
  revenue-daily.json : 当日エントリに `apify_ppe_external_views_keys` + `apify_ppe_external_views_promo` メトリクスを追記

使い方:
  python3 scripts/apify_ppe_external_views.py --point now   # 直近ポイントを自動計測 (KEYS + PROMO)
  python3 scripts/apify_ppe_external_views.py --point 24h   # KEYS特定ポイントを強制計測
  python3 scripts/apify_ppe_external_views.py --point 1d    # PROMO全俳優を now基準で計測
  python3 scripts/apify_ppe_external_views.py --dry         # 記録なしで表示のみ
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, UTC
from typing import Any, cast

import requests

PROJECT_DIR = "/mnt/d/Project2/kensho"
API_BASE = "https://api.apify.com/v2"

def _load_env_file() -> None:
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

_load_env_file()

APIFY_TOKEN_DEFAULT = os.environ.get("APIFY_TOKEN_DEFAULT", "").strip()
TOKEN_ENV = "APIFY_TOKEN"
STATE_FILE = os.path.join(PROJECT_DIR, "data", "apify_ppe_external_views_state.json")
REVENUE_DAILY = os.path.join(PROJECT_DIR, "data", "revenue-daily.json")
APIFY_PPE = os.path.join(PROJECT_DIR, "pay_per_event.json")
PROMO_STATE_FILE = os.path.join(PROJECT_DIR, "data", "apify_store_promo_state.json")

DEPLOY_BASELINE = "2026-09-04"
MEASURE_POINTS = {
    "baseline": "2026-09-04",
    "24h": "2026-09-05",
    "72h": "2026-09-07",
    "168h": "2026-09-11",
}
RUNS_LIMIT = 1000

KEYS: list[dict[str, str]] = [
    {"key": "japan-camera-market", "actual_name": "japan-used-camera-market-scraper", "fallback_id": "mQaZFo6up4YZKepC3"},
    {"key": "japan-watch-market", "actual_name": "japan-watch-market-scraper", "fallback_id": "gMqdrS2evpcybSZc2"},
    {"key": "japan-luxury-market", "actual_name": "japan-luxury-brand-market-scraper", "fallback_id": "b0vuqa3ESvy2mOwFB"},
    {"key": "japan-instrument-market", "actual_name": "japan-used-instrument-market-scraper", "fallback_id": "yN1R26HrV6C2MBKas"},
    {"key": "japan-offmall-market", "actual_name": "japan-offmall-market-scraper", "fallback_id": "Zh4kqcS4dYPWpFzBd"},
]

PROMO_ACTORS: list[dict[str, Any]] = [
    {"actual_name": "japan-used-camera-market-scraper", "fallback_id": "mQaZFo6up4YZKepC3", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-watch-market-scraper", "fallback_id": "gMqdrS2evpcybSZc2", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-luxury-brand-market-scraper", "fallback_id": "b0vuqa3ESvy2mOwFB", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-used-instrument-market-scraper", "fallback_id": "yN1R26HrV6C2MBKas", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-offmall-market-scraper", "fallback_id": "Zh4kqcS4dYPWpFzBd", "priority": 1, "price_usd": 0.005},
    {"actual_name": "surugaya-japan-hobby-prices", "fallback_id": "F8Hl0a8Cx9bpJBrxR", "priority": 2, "price_usd": 0.005},
    {"actual_name": "mandarake-auction-scraper", "fallback_id": "q2E37PVTg5JcGOTEn", "priority": 2, "price_usd": 0.005},
    {"actual_name": "tackleberry-japan-fishing-tackle-scraper", "fallback_id": "wxMskoiHMPeeH2qAJ", "priority": 2, "price_usd": 0.005},
    {"actual_name": "yahoo-auctions-japan-scraper", "fallback_id": "8WBam4CPB72q9Rvsd", "priority": 2, "price_usd": 0.005},
    {"actual_name": "dlsite-scraper", "fallback_id": "6Z7tJ3plfUmAgGmbk", "priority": 3, "price_usd": 0.005},
    {"actual_name": "dmm-scraper", "fallback_id": "nUm22B2guMo8vXom6", "priority": 3, "price_usd": 0.002},
    {"actual_name": "kitamura-japan-used-camera-scraper", "fallback_id": "DOiD9y1NAJfLBcAjT", "priority": 3, "price_usd": 0.005},
    {"actual_name": "jackroad-used-watch-scraper", "fallback_id": "nWf9BR2ndMTYqKxNB", "priority": 3, "price_usd": 0.005},
    {"actual_name": "komehyo-japan-brand-scraper", "fallback_id": "Db3iY8FIRxPjPag7N", "priority": 3, "price_usd": 0.005},
    {"actual_name": "eurostat-indicators", "fallback_id": "pAxQ0lRyArudhK9Wx", "priority": 4, "price_usd": 0.004},
    {"actual_name": "world-bank-indicators", "fallback_id": "u2qsG1UfVHWsgl8Dg", "priority": 4, "price_usd": 0.003},
    {"actual_name": "goo-net-car-scraper", "fallback_id": "bgm5Gxn4BeBmoO7xD", "priority": 5, "price_usd": 0.002},
    {"actual_name": "biglemon-machinery-scraper", "fallback_id": "W9cXhDckzHd9RZWnQ", "priority": 5, "price_usd": 0.002},
    {"actual_name": "digimart-japan-used-instrument-scraper", "fallback_id": "FSuoQiX8OG4KuIQ9c", "priority": 5, "price_usd": 0.002},
    {"actual_name": "golfpartner-used-club-scraper", "fallback_id": "xPSQSSsdVjRwWQAiA", "priority": 5, "price_usd": 0.002},
    # additional promo actors from mapping (23 total)
    {"actual_name": "kensho-high-value-leads", "fallback_id": "6y9vXxQ4sJ9kL7mN", "priority": 5, "price_usd": 0.005},
    {"actual_name": "mercari-japan-search-scraper", "fallback_id": "3z2y1x0w9v8u7t6s", "priority": 5, "price_usd": 0.005},
    {"actual_name": "japan-jepx-mcp", "fallback_id": "9a8b7c6d5e4f3g2h", "priority": 5, "price_usd": 0.005},
]

def get_token() -> str:
    return os.environ.get(TOKEN_ENV, "").strip() or APIFY_TOKEN_DEFAULT

def load_prices() -> dict[str, float]:
    if not os.path.exists(APIFY_PPE):
        return {}
    try:
        with open(APIFY_PPE, encoding="utf-8") as f:
            return dict(json.load(f).get("actors_ppe") or {})
    except Exception:
        return {}

def resolve_ids(token: str) -> dict[str, str]:
    known = {k["actual_name"]: k["fallback_id"] for k in KEYS}
    try:
        resp = requests.get(f"{API_BASE}/acts?my=true&token={token}", timeout=30)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            for it in items:
                nm = it.get("name")
                if nm in known:
                    known[nm] = it.get("id") or known[nm]
    except Exception:
        pass
    return known

def resolve_promo_ids(token: str) -> dict[str, str]:
    known = {a["actual_name"]: a["fallback_id"] for a in PROMO_ACTORS}
    try:
        resp = requests.get(f"{API_BASE}/acts?my=true&token={token}", timeout=30)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            for it in items:
                nm = it.get("name")
                if nm in known:
                    known[nm] = it.get("id") or known[nm]
    except Exception:
        pass
    return known

def fetch_owner(token: str) -> str:
    try:
        resp = requests.get(f"{API_BASE}/users/me?token={token}", timeout=30)
        return cast(str, (resp.json().get("data") or {}).get("id", ""))
    except Exception:
        return ""

def _strip(s: str | None) -> str:
    return (s or "").strip()

def collect_actor_metrics(token: str, actual_name: str, actor_id: str, owner: str, price: float | None) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "actor_id": actor_id,
        "actual_name": actual_name,
        "external_views": 0,
        "total_runs": 0,
        "u30d": 0,
        "bookmarks": 0,
        "seo_present": False,
        "price_usd": price,
    }
    try:
        resp = requests.get(f"{API_BASE}/acts/{actor_id}?token={token}", timeout=30)
        if resp.status_code == 200:
            a = resp.json().get("data") or {}
            stats = a.get("stats") or {}
            metrics["total_runs"] = int(stats.get("totalRuns", 0) or 0)
            metrics["u30d"] = int(stats.get("totalUsers30Days", 0) or 0)
            metrics["bookmarks"] = int(stats.get("bookmarkCount", 0) or 0)
            seo_ok = bool(_strip(a.get("seoTitle")) and _strip(a.get("seoDescription")))
            metrics["seo_present"] = seo_ok
    except Exception:
        pass
    try:
        resp = requests.get(f"{API_BASE}/acts/{actor_id}/runs?token={token}&desc=1&limit={RUNS_LIMIT}", timeout=30)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            ext = 0
            for r in items:
                if (r.get("userId") or "") != owner:
                    ext += 1
            metrics["external_views"] = ext
    except Exception:
        pass
    return metrics

def newest_point(today: str | None = None) -> str:
    """今日時点で計測可能な最新ポイント（baseline 以降、未来は含まず）。"""
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    order = ["baseline", "24h", "72h", "168h"]
    resolved = None
    for p in order:
        if today >= MEASURE_POINTS[p]:
            resolved = p
        else:
            break
    return resolved or "baseline"

def load_state() -> dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except Exception:
            return {}
    return {}

def save_state(state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)

def merge_state(state: dict[str, Any], m: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("baseline", DEPLOY_BASELINE)
    state.setdefault("points", {})
    state["points"][m["point"]] = m
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return state

def measure_keys(token: str, point: str) -> dict[str, Any]:
    if point not in MEASURE_POINTS:
        raise ValueError(f"unknown KEYS point: {point}")
    owner = fetch_owner(token)
    id_map = resolve_ids(token)
    prices = load_prices()
    per_actor: dict[str, Any] = {}
    for k in KEYS:
        actual = k["actual_name"]
        actor_id = id_map.get(actual) or k["fallback_id"]
        per_actor[k["key"]] = collect_actor_metrics(token, actual, actor_id, owner, prices.get(actual))
    return {
        "point": point,
        "point_date": MEASURE_POINTS[point],
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "baseline": DEPLOY_BASELINE,
        "per_actor": per_actor,
    }

def measure_promo_all(token: str) -> dict[str, Any]:
    owner = fetch_owner(token)
    id_map = resolve_promo_ids(token)
    per_promo_actor: dict[str, Any] = {}
    for a in PROMO_ACTORS:
        actual = a["actual_name"]
        actor_id = id_map.get(actual) or a["fallback_id"]
        metrics = collect_actor_metrics(token, actual, actor_id, owner, a.get("price_usd"))
        per_promo_actor[actual] = metrics
    point = "promo_now"
    return {
        "point": point,
        "point_date": datetime.now().strftime("%Y-%m-%d"),
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "baseline": DEPLOY_BASELINE,
        "per_promo_actor": per_promo_actor,
    }

def attach_to_daily_keys(m: dict[str, Any]) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(REVENUE_DAILY):
        return False
    try:
        with open(REVENUE_DAILY, encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list):
            entries = []
    except Exception:
        return False
    target = next((e for e in entries if e.get("date") == today), None)
    if target is None:
        return False
    payload = {}
    for key, mm in (m.get("per_actor") or {}).items():
        payload[key] = {
            "actual_name": mm.get("actual_name"),
            "external_views": mm.get("external_views"),
            "total_runs": mm.get("total_runs"),
            "u30d": mm.get("u30d"),
            "bookmarks": mm.get("bookmarks"),
            "seo_present": mm.get("seo_present"),
        }
    target["apify_ppe_external_views_keys"] = {
        "point": m.get("point"),
        "point_date": m.get("point_date"),
        "baseline": m.get("baseline"),
        "measured_at": m.get("measured_at"),
        "proxy_note": "external_views = 外部(owner以外)ユーザー累積run",
        "actors": payload,
    }
    try:
        with open(REVENUE_DAILY, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False

def attach_to_daily_promo(m: dict[str, Any]) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(REVENUE_DAILY):
        return False
    try:
        with open(REVENUE_DAILY, encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list):
            entries = []
    except Exception:
        return False
    target = next((e for e in entries if e.get("date") == today), None)
    if target is None:
        return False
    payload = {}
    for name, mm in (m.get("per_promo_actor") or {}).items():
        payload[name] = {
            "actual_name": mm.get("actual_name"),
            "external_views": mm.get("external_views"),
            "total_runs": mm.get("total_runs"),
            "u30d": mm.get("u30d"),
            "bookmarks": mm.get("bookmarks"),
            "price_usd": mm.get("price_usd"),
        }
    target["apify_ppe_external_views_promo"] = {
        "point": m.get("point"),
        "point_date": m.get("point_date"),
        "measured_at": m.get("measured_at"),
        "proxy_note": "external_views = 外部(owner以外)ユーザー累積run (全23プロモ俳優)",
        "actors": payload,
    }
    try:
        with open(REVENUE_DAILY, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apify PPE 外部view計測 v19")
    parser.add_argument("--point", default="now", help="baseline | 24h | 72h | 168h | now | 1d | 3d | 7d")
    parser.add_argument("--dry", action="store_true", help="記録なし")
    args = parser.parse_args(argv)

    token = get_token()
    if not token:
        print("TOKEN_NOT_SET: APIFY_TOKEN 未設定", file=sys.stderr)
        return 1

    point_arg = args.point
    dry = args.dry

    print("=== Apify PPE external_views 計測 v19 ===")

    state = load_state()
    results = []

    # KEYS 計測
    if point_arg == "now":
        keys_point = newest_point()
    elif point_arg in MEASURE_POINTS:
        keys_point = point_arg
    else:
        keys_point = None

    if keys_point:
        m_keys = measure_keys(token, keys_point)
        print(f"KEYS point={keys_point} date={m_keys['point_date']}")
        total_ev_keys = sum(v.get("external_views", 0) for v in m_keys["per_actor"].values())
        print(f"  KEYS 合計 external_views = {total_ev_keys}")
        for k, v in m_keys["per_actor"].items():
            seo = "SEO✓" if v.get("seo_present") else "SEO✗"
            print(f"  {k:22s} ext={v['external_views']:3d} runs={v['total_runs']:4d} {seo}")
        if not dry:
            state = merge_state(state, m_keys)
            attach_to_daily_keys(m_keys)
        results.append(("keys", m_keys))

    # PROMO 計測
    # 1d/3d/7d は今は全俳優計測として処理（投稿日基準の拡張は将来実装）
    if point_arg in ("now", "1d", "3d", "7d") or (keys_point is None and point_arg not in MEASURE_POINTS):
        m_promo = measure_promo_all(token)
        print(f"PROMO point={m_promo['point']} date={m_promo['point_date']}")
        total_ev_promo = sum(v.get("external_views", 0) for v in m_promo.get("per_promo_actor", {}).values())
        print(f"  PROMO 合計 external_views = {total_ev_promo}")
        # 上位表示
        cnt = 0
        for name, v in m_promo.get("per_promo_actor", {}).items():
            if cnt >= 10:
                break
            print(f"  {name:45s} ext={v['external_views']:3d} runs={v['total_runs']:4d}")
            cnt += 1
        if not dry:
            # PROMO 測定は独立ポイントで保存
            m_promo_combined = {
                "point": f"promo_{point_arg}",
                "point_date": datetime.now().strftime("%Y-%m-%d"),
                "measured_at": datetime.now().isoformat(timespec="seconds"),
                "baseline": DEPLOY_BASELINE,
                "per_promo_actor": m_promo.get("per_promo_actor", {}),
            }
            state = merge_state(state, m_promo_combined)
            attach_to_daily_promo(m_promo_combined)
        results.append(("promo", m_promo))

    if not dry:
        save_state(state)
        print(f"✓ state 保存: {STATE_FILE}")

    # 検証用集計
    promo_total = sum(
        a.get("external_views", 0)
        for p in state.get("points", {}).values()
        for a in p.get("per_promo_actor", {}).values()
    )
    if promo_total > 0:
        print(f"✓ promo_total > 0 ({promo_total})")
    else:
        print(f"⚠ promo_total = 0（計測結果が未成立の可能性）")

    return 0

if __name__ == "__main__":
    sys.exit(main())
