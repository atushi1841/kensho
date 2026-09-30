#!/usr/bin/env python3
"""apify_post_promo_tracker — 投稿 tweet_id 起点の動的 external_views 追跡.

背景:
- t_ee861eb5/t_bea4c6c7 で real tweet_id 取得済み (2104655287496114428, 9/29投稿)
- 既存の apify_ppe_external_views.py は v15-A baseline(9/4) 固定の MEASURE_POINTS のみ
- 本タスク: 投稿日 +1/+3/+7 日の動的ポイントで自動計測 → revenue-daily.json 記録

仕様:
- 入力: data/apify_store_promo_state.json の tweet_id + posted_at
- 計測ポイント: 投稿日+1日 / +3日 / +7日 (JST基準)
- 対象アクター: slot b 投稿で紹介した 3 アクター
  - mandarake-auction-scraper, dlsite-scraper, tackleberry-japan-fishing-tackle-scraper
- 外部view取得: /acts/{actor_id}/runs で owner 以外の run を累積カウント (同一プロキシ手法)
- 出力: data/apify_post_promo_tracker_state.json (履歴) + revenue-daily.json 当日エントリ追記

使い方:
  python3 scripts/apify_post_promo_tracker.py --point now   # 直近ポイントを自動計測
  python3 scripts/apify_post_promo_tracker.py --point 1d    # 特定ポイントを強制計測
  python3 scripts/apify_post_promo_tracker.py --dry         # 記録なしで表示のみ
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any, cast

import requests

PROJECT_DIR = "/mnt/d/Project2/kensho"
API_BASE = "https://api.apify.com/v2"

# ── 簡易.envローダー ──
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

STATE_FILE = os.path.join(PROJECT_DIR, "data", "apify_post_promo_tracker_state.json")
PROMO_STATE_FILE = os.path.join(PROJECT_DIR, "data", "apify_store_promo_state.json")
REVENUE_DAILY = os.path.join(PROJECT_DIR, "data", "revenue-daily.json")

# 追跡対象アクター (slot b 投稿で紹介された 3 アクター)
# actual_name → fallback_id
TRACKED_ACTORS: dict[str, str] = {
    "mandarake-auction-scraper": "q2E37PVTg5JcGOTEn",
    "dlsite-scraper": "6Z7tJ3plfUmAgGmbk",
    "tackleberry-japan-fishing-tackle-scraper": "wxMskoiHMPeeH2qAJ",
}

# run 一覧取得の最大件数
RUNS_LIMIT = 1000


def get_token() -> str:
    return os.environ.get(TOKEN_ENV, "").strip() or APIFY_TOKEN_DEFAULT


def _strip(s: str | None) -> str:
    return (s or "").strip()


def load_promo_state() -> dict[str, Any]:
    """apify_store_promo_state.json から最新投稿の tweet_id と posted_at を取得。"""
    if not os.path.exists(PROMO_STATE_FILE):
        return {}
    try:
        with open(PROMO_STATE_FILE, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))
    except Exception:
        return {}


def get_latest_post_info() -> tuple[str | None, str | None, list[str]]:
    """
    最新投稿の tweet_id, posted_at(JST日付), 対象アクター名リストを返す。
    なければ (None, None, [])。
    """
    state = load_promo_state()
    posted_weeks = state.get("posted_weeks", {})
    if not posted_weeks:
        return None, None, []
    # 最新週を取得
    latest_week = max(posted_weeks.keys())
    week_data = posted_weeks[latest_week]
    # slot b を優先、なければ a
    for slot in ("b", "a"):
        if slot in week_data:
            slot_data = week_data[slot]
            tweet_id = slot_data.get("tweet_id")
            posted_at = slot_data.get("posted_at")
            actors = slot_data.get("actors", [])
            if tweet_id and posted_at and not tweet_id.startswith("placeholder"):
                # JST日付抽出 (ISO形式から日付部分のみ)
                post_date = posted_at[:10]  # "2026-09-29T04:32:14" -> "2026-09-29"
                return tweet_id, post_date, actors
    return None, None, []


def compute_measure_points(post_date: str) -> dict[str, str]:
    """
    投稿日から動的計測ポイントを計算。
    Returns: {point_name: date_str} e.g. {"1d": "2026-09-30", "3d": "2026-10-02", "7d": "2026-10-06"}
    """
    base = datetime.strptime(post_date, "%Y-%m-%d")
    return {
        "1d": (base + timedelta(days=1)).strftime("%Y-%m-%d"),
        "3d": (base + timedelta(days=3)).strftime("%Y-%m-%d"),
        "7d": (base + timedelta(days=7)).strftime("%Y-%m-%d"),
    }


def newest_point(measure_points: dict[str, str], today: str | None = None) -> str | None:
    """今日時点で計測可能な最新ポイント（過去のみ、未来は含まず）。JST基準で判定。"""
    if today is None:
        # JST基準の今日の日付を使用（cronは 05:00 JST 実行想定）
        today = datetime.now().astimezone().strftime("%Y-%m-%d")
    order = ["1d", "3d", "7d"]
    resolved = None
    for p in order:
        if today >= measure_points[p]:
            resolved = p
        else:
            break
    return resolved


def resolve_ids(token: str, actor_names: list[str]) -> dict[str, str]:
    """実API名 → actor_id を /acts から解決。失敗時はフォールバック id を使用。"""
    known = {name: TRACKED_ACTORS[name] for name in actor_names if name in TRACKED_ACTORS}
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


def collect_actor_metrics(
    token: str,
    actual_name: str,
    actor_id: str,
    owner: str,
) -> dict[str, Any]:
    """1 アクター分の metrics を Apify API から集計。"""
    metrics: dict[str, Any] = {
        "actor_id": actor_id,
        "actual_name": actual_name,
        "external_views": 0,
        "total_runs": 0,
        "u30d": 0,
        "bookmarks": 0,
    }
    # 1) actor 詳細（stats）
    try:
        resp = requests.get(f"{API_BASE}/acts/{actor_id}?token={token}", timeout=30)
        if resp.status_code == 200:
            a = resp.json().get("data") or {}
            stats = a.get("stats") or {}
            metrics["total_runs"] = int(stats.get("totalRuns", 0) or 0)
            metrics["u30d"] = int(stats.get("totalUsers30Days", 0) or 0)
            metrics["bookmarks"] = int(stats.get("bookmarkCount", 0) or 0)
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


def measure(token: str, point: str, measure_points: dict[str, str], actor_names: list[str], post_date: str) -> dict[str, Any]:
    """指定ポイントで全追跡アクターを計測。"""
    if point not in measure_points:
        raise ValueError(f"unknown point: {point} (expected: {list(measure_points)})")
    owner = fetch_owner(token)
    id_map = resolve_ids(token, actor_names)
    per_actor: dict[str, Any] = {}
    for name in actor_names:
        actor_id = id_map.get(name) or TRACKED_ACTORS.get(name, "")
        if actor_id:
            per_actor[name] = collect_actor_metrics(token, name, actor_id, owner)
    return {
        "point": point,
        "point_date": measure_points[point],
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "post_date": post_date,
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
    state.setdefault("post_date", m.get("post_date"))
    state.setdefault("points", {})[m["point"]] = m
    state["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return state


def attach_to_daily(m: dict[str, Any]) -> bool:
    """revenue-daily.json の当日エントリに追記。"""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
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
    payload: dict[str, Any] = {}
    for key, mm in (m.get("per_actor") or {}).items():
        payload[key] = {
            "actual_name": mm.get("actual_name"),
            "external_views": mm.get("external_views"),
            "total_runs": mm.get("total_runs"),
            "u30d": mm.get("u30d"),
            "bookmarks": mm.get("bookmarks"),
        }
    entry_metric = {
        "point": m.get("point"),
        "point_date": m.get("point_date"),
        "post_date": m.get("post_date"),
        "measured_at": m.get("measured_at"),
        "proxy_note": "external_views = 外部(owner以外)ユーザー累積run (投稿tweet_id起点の動的追跡)",
        "actors": payload,
    }
    target["apify_post_promo_tracker"] = entry_metric
    try:
        with open(REVENUE_DAILY, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="投稿起点 Apify PPE 外部view動的追跡")
    parser.add_argument("--point", default="now", help="1d | 3d | 7d | now(直近自動)")
    parser.add_argument("--dry", action="store_true", help="記録・保存なしで表示のみ")
    args = parser.parse_args(argv)

    token = get_token()

    # 投稿情報取得
    tweet_id, post_date, actor_names = get_latest_post_info()
    if not tweet_id or not post_date or not actor_names:
        print("✗ 投稿情報が見つかりません (apify_store_promo_state.json に有効な投稿なし)", file=sys.stderr)
        return 1

    # 計測ポイント計算
    measure_points = compute_measure_points(post_date)

    point = newest_point(measure_points) if args.point == "now" else args.point
    if point is None:
        print("=== Apify Post-Promo external_views 動的追跡 ===")
        print(f"  元投稿: tweet_id={tweet_id}  date={post_date}")
        print(f"  対象アクター: {', '.join(actor_names)}")
        print("  計測可能なポイントなし（全て未来日付）— スキップ")
        return 0
    if point not in measure_points:
        print(f"✗ 不明なポイント '{point}'。指定可能: {list(measure_points)} / now", file=sys.stderr)
        return 2

    print(f"=== Apify Post-Promo external_views 動的追跡 ===")
    print(f"  元投稿: tweet_id={tweet_id}  date={post_date}")
    print(f"  対象アクター: {', '.join(actor_names)}")
    print(f"  計測ポイント: {point}  日付: {measure_points[point]}")

    m = measure(token, point, measure_points, actor_names, post_date)

    total_ev = 0
    for key, mm in m["per_actor"].items():
        total_ev += mm["external_views"]
        print(
            f"  {key:45s} ext_views={mm['external_views']:>3d}  runs={mm['total_runs']:>4d}"
            f"  u30d={mm['u30d']}  bm={mm['bookmarks']}"
        )
    print(f"  合計 external_views(proxy) = {total_ev}")

    if args.dry:
        return 0

    state = merge_state(load_state(), m)
    save_state(state)
    print(f"✓ state 保存: {STATE_FILE}")

    wrote = attach_to_daily(m)
    if wrote:
        print(f"✓ revenue-daily.json に apify_post_promo_tracker 追記")
    else:
        print("⚠ 当日エントリが revenue-daily.json に無いため metric 未追記（state は保存済み）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())