#!/usr/bin/env python3
"""apify_ppe_external_views — v18-B Apify PPE アクター外部ビュー計測レイヤー（t_b6684e7b）。

revenue-critic v15-A（t_90fce3df）で適用した**説明文（description / seoTitle /
seoDescription）一括テンプレーティング**が、Apify Store の CTR（サーチ結果→画面
到達→使用）に与える影響を、PPE 課金アクター top5 について 24h/72h/168h 後まで
追跡する。

計測対象（KEYS）:
  japan-camera-market, japan-watch-market, japan-luxury-market,
  japan-instrument-market, japan-offmall-market

指標の定義:
  external_views : **外部（owner 以外）ユーザーの累積 run 数**。Apify 公開 API は
                   Store ページの view 数を直接公開しておらず、外部エンゲージメント
                   （Store CTR の下方ファネル）を測れる唯一の公開シグナルが
                   「userId != owner の run」であるため、これを external views の
                   proxy とする（ドキュメント: 制限を明記）。
  補助シグナル   : total_runs（累積）, u30d（新規流入）, bookmarks, seo_present
                   （説明文テンプレーティング適用の有無 = 処置フラグ）。

測定ポイント（v15-A deploy 日 = 2026-09-04 基準）:
  baseline : 2026-09-04（適用当日）
  24h      : 2026-09-05
  72h      : 2026-09-07
  168h     : 2026-09-11

出力:
  data/apify_ppe_external_views_state.json   : 全ポイント累積（per-actor 時系列）
  revenue-daily.json : 当日エントリに `apify_ppe_external_views_keys` メトリクスを追記

使い方:
  python3 scripts/apify_ppe_external_views.py --point now   # 直近ポイントを自動計測
  python3 scripts/apify_ppe_external_views.py --point 24h   # 特定ポイントを強制計測
  python3 scripts/apify_ppe_external_views.py --dry         # 記録なしで表示のみ
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, cast

import requests

PROJECT_DIR = "/mnt/d/Project2/kensho"
API_BASE = "https://api.apify.com/v2"


# ── 簡易.envローダー（9/9追加: トークン直打ち除去。kensho_revenue_collect.pyと同実装） ──
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
        pass  # .env読み取り失敗しても継続


_load_env_file()

APIFY_TOKEN_DEFAULT = os.environ.get("APIFY_TOKEN_DEFAULT", "").strip()  # 値は.envにのみ（git管理外）
TOKEN_ENV = "APIFY_TOKEN"

STATE_FILE = os.path.join(PROJECT_DIR, "data", "apify_ppe_external_views_state.json")
REVENUE_DAILY = os.path.join(PROJECT_DIR, "data", "revenue-daily.json")
APIFY_PPE = os.path.join(PROJECT_DIR, "pay_per_event.json")

# v15-A 一括テンプレーティングの適用日（baseline）。
DEPLOY_BASELINE = "2026-09-04"
# 測定ポイント日（baseline から 24h/72h/168h 後）。
MEASURE_POINTS: dict[str, str] = {
    "baseline": "2026-09-04",
    "24h": "2026-09-05",
    "72h": "2026-09-07",
    "168h": "2026-09-11",
}

# top5 PPE アクター（ポートフォリオキー short_name → 実 API 名）。
# actor id は実行時に /acts から実名で解決し、取得失敗時は既知 id にフォールバック。
KEYS: list[dict[str, str]] = [
    {
        "key": "japan-camera-market",
        "actual_name": "japan-used-camera-market-scraper",
        "fallback_id": "mQaZFo6up4YZKepC3",
    },
    {"key": "japan-watch-market", "actual_name": "japan-watch-market-scraper", "fallback_id": "gMqdrS2evpcybSZc2"},
    {
        "key": "japan-luxury-market",
        "actual_name": "japan-luxury-brand-market-scraper",
        "fallback_id": "b0vuqa3ESvy2mOwFB",
    },
    {
        "key": "japan-instrument-market",
        "actual_name": "japan-used-instrument-market-scraper",
        "fallback_id": "yN1R26HrV6C2MBKas",
    },
    {"key": "japan-offmall-market", "actual_name": "japan-offmall-market-scraper", "fallback_id": "Zh4kqcS4dYPWpFzBd"},
]

# run 一覧取得の最大件数（外部 view の累積カウントに十分な履歴）。総 run は最大〜数百。
RUNS_LIMIT = 1000


def get_token() -> str:
    return os.environ.get(TOKEN_ENV, "").strip() or APIFY_TOKEN_DEFAULT


def load_prices() -> dict[str, float]:
    """pay_per_event.json の actors_ppe（実API名 → 単価）を読み込む。"""
    if not os.path.exists(APIFY_PPE):
        return {}
    try:
        with open(APIFY_PPE, encoding="utf-8") as f:
            return dict(json.load(f).get("actors_ppe") or {})
    except Exception:
        return {}


def resolve_ids(token: str) -> dict[str, str]:
    """実API名 → actor id を /acts から解決。失敗時はフォールバック id を使用。"""
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


def fetch_owner(token: str) -> str:
    resp = requests.get(f"{API_BASE}/users/me?token={token}", timeout=30)
    return cast(str, (resp.json().get("data") or {}).get("id", ""))


def _strip(s: str | None) -> str:
    return (s or "").strip()


def collect_actor_metrics(
    token: str,
    actual_name: str,
    actor_id: str,
    owner: str,
    price: float | None,
) -> dict[str, Any]:
    """1 アクター分の metrics を Apify API から集計。"""
    metrics: dict[str, Any] = {
        "actor_id": actor_id,
        "actual_name": actual_name,
        "external_views": 0,  # proxy = 外部(owner以外)累積run
        "total_runs": 0,
        "u30d": 0,
        "bookmarks": 0,
        "seo_present": False,
        "price_usd": price,
    }
    # 1) actor 詳細（stats / seo title,desc）
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
    # 2) runs 一覧で外部 run（owner 以外）を累積カウント
    try:
        resp = requests.get(
            f"{API_BASE}/acts/{actor_id}/runs?token={token}&desc=1&limit={RUNS_LIMIT}",
            timeout=30,
        )
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
    # ポイント日一覧を昇順に
    order = ["baseline", "24h", "72h", "168h"]
    resolved = None
    for p in order:
        if today >= MEASURE_POINTS[p]:
            resolved = p
        else:
            break
    return resolved or "baseline"


def measure(token: str, point: str) -> dict[str, Any]:
    """指定ポイントで全 KEYS アクターを計測。"""
    if point not in MEASURE_POINTS:
        raise ValueError(f"unknown point: {point} (expected: {list(MEASURE_POINTS)})")
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
    """同一ポイントは上書き、それ以外は追記マージ。"""
    state.setdefault("baseline", DEPLOY_BASELINE)
    state.setdefault("points", {})[m["point"]] = m
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return state


def attach_to_daily(m: dict[str, Any]) -> bool:
    """revenue-daily.json の当日エントリに `apify_ppe_external_views_keys` を追記。"""
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
    target = None
    for e in entries:
        if e.get("date") == today:
            target = e
            break
    if target is None:
        return False
    # シンプルな形状: {key: {actual_name, external_views, total_runs, u30d, bookmarks, seo_present}}
    payload: dict[str, Any] = {}
    for key, mm in (m.get("per_actor") or {}).items():
        payload[key] = {
            "actual_name": mm.get("actual_name"),
            "external_views": mm.get("external_views"),
            "total_runs": mm.get("total_runs"),
            "u30d": mm.get("u30d"),
            "bookmarks": mm.get("bookmarks"),
            "seo_present": mm.get("seo_present"),
        }
    entry_metric = {
        "point": m.get("point"),
        "point_date": m.get("point_date"),
        "baseline": m.get("baseline"),
        "measured_at": m.get("measured_at"),
        "proxy_note": (
            "external_views = 外部(owner以外)ユーザー累積run (Apify公開APIで唯一取得可能な外部エンゲージメント信号)"
        ),
        "actors": payload,
    }
    target["apify_ppe_external_views_keys"] = entry_metric
    try:
        with open(REVENUE_DAILY, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apify PPE 外部view計測 (v18-B)")
    parser.add_argument("--point", default="now", help="baseline | 24h | 72h | 168h | now(直近自動)")
    parser.add_argument("--dry", action="store_true", help="記録・保存なしで表示のみ")
    args = parser.parse_args(argv)

    token = get_token()
    point = newest_point() if args.point == "now" else args.point
    if point not in MEASURE_POINTS:
        print(f"✗ 不明なポイント '{point}'。指定可能: baseline/24h/72h/168h/now", file=sys.stderr)
        return 2

    m = measure(token, point)
    print("=== Apify PPE external_views 計測 ===")
    print(f"  ポイント: {m['point']}  日付: {m['point_date']}  baseline: {m['baseline']}")
    print(f"  計測時刻: {m['measured_at']}")
    total_ev = 0
    for key, mm in m["per_actor"].items():
        total_ev += mm["external_views"]
        seo = "SEO✓" if mm["seo_present"] else "SEO✗"
        print(
            f"  {key:22s} ext_views={mm['external_views']:>3d}  runs={mm['total_runs']:>4d}"
            f"  u30d={mm['u30d']}  bm={mm['bookmarks']}  {seo}"
        )
    print(f"  合計 external_views(proxy) = {total_ev}")

    if args.dry:
        return 0

    state = merge_state(load_state(), m)
    save_state(state)
    print(f"✓ state 保存: {STATE_FILE}")

    wrote = attach_to_daily(m)
    if wrote:
        print(f"✓ revenue-daily.json に {today_entry_note()} 追記")
    else:
        print("⚠ 当日エントリが revenue-daily.json に無いため metric 未追記（state は保存済み）", file=sys.stderr)
    return 0


def today_entry_note() -> str:
    return "apify_ppe_external_views_keys"


if __name__ == "__main__":
    sys.exit(main())
