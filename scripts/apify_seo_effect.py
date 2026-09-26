#!/usr/bin/env python3
"""apify_seo_effect — Apify SEO batch 効果測定（revenue-critic v16-A / t_21a7df50）。

v14-C（t_15af8300、2026-09-04）で適用した SEO バッチ（19+1 アクターの
description / categories / seoTitle 等）が、アクター使用量に与えた効果を
revenue-daily.json から per-actor で測る。測定ポイント:
  - baseline : 2026-09-04（SEO適用当日）
  - point 1  : 2026-09-05（24h後）
  - point 2  : 2026-09-07（72h後）
  - point 3  : 2026-09-11（168h後）

指標:
  - runs    : 累積runs（増加 = 流入増）
  - u30d    : totalUsers30Days（増加 = 新規ユーザー流入の兆候）
  - daily   : 前回ポイントからの1日あたりruns増分（runs間引きで算出）

出力（reports/apify-seo/）:
  - apify-seo-effect-<date>.json  : 現行ポイントの per-actor 計測サマリ
  - apify-seo-effect.json         : 全ポイント累積（追記マージ）

使い方:
  python3 scripts/apify_seo_effect.py            # 最新利用可能ポイントを計測
  python3 scripts/apify_seo_effect.py --date 2026-09-07  # 指定日を強制計測
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any

PROJECT_DIR = "/mnt/d/Project2/kensho"
DATA_FILE = os.path.join(PROJECT_DIR, "data", "revenue-daily.json")
OUT_DIR = os.path.join(PROJECT_DIR, "reports", "apify-seo")
ACCUM_FILE = os.path.join(OUT_DIR, "apify-seo-effect.json")

# SEO適用日（baseline）と測定ポイント。revenue-daily.json に日次集計が無い日は
# 直近の前日エントリで代用（後述の _closest で解決）。
BASELINE_DATE = "2026-09-04"
MEASURE_POINTS = ["2026-09-05", "2026-09-07", "2026-09-11"]

# 0改善と判定する閾値（baseline→ポイントで runs が増えていない or u30d が増えていない）
ZERO_IMPROVE_RUNS_DELTA = 0
ZERO_IMPROVE_U30D_DELTA = 0


def _clamp_date(date_str: str, available: list[str]) -> str:
    """available に date_str が無い場合、最も近い日付を返す（データ欠損時）。
    未来のポイント日 → 直近の過去データ；過去の日付 → 利用可能な最古に近い日。
    """
    if date_str in available:
        return date_str
    if not available:
        return ""
    return min(available, key=lambda d: abs(_days_between(d, date_str)))


def load_daily() -> list[dict[str, Any]]:
    """revenue-daily.json を読み込み、日付昇順リストを返す。"""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
        return data if isinstance(data, list) else []


def build_actor_series(
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, int]]]:
    """{actor_portfolio_name: {date: {runs, u30d}}} を構築。

    actor キーは revenue-daily.json の `details[].name`（ポートフォリオ名、
    例: japan-camera-market）。実際の API 名は `actual_name` フィールドに。
    """
    series: dict[str, dict[str, dict[str, int]]] = {}
    for e in entries:
        dt = e.get("date", "")
        ap = e.get("apify", {})
        for d in ap.get("details", []):
            name = d.get("name") or d.get("actual_name")
            if not name:
                continue
            series.setdefault(name, {})[dt] = {
                "runs": int(d.get("runs", 0)),
                "u30d": int(d.get("u30d", 0)),
            }
    return series


def measure_point(
    series: dict[str, dict[str, dict[str, int]]],
    baseline_date: str,
    point_date: str,
) -> dict[str, Any]:
    """baseline→point の per-actor 差分を計算。"""
    available = sorted({d for rows in series.values() for d in rows})
    b = _clamp_date(baseline_date, available)
    p = _clamp_date(point_date, available)
    # ポイント日が baseline 以前なら測れない
    if not b or not p or p < b:
        return {
            "baseline": b,
            "point": p,
            "error": "point date earlier than baseline or data missing",
            "actors": {},
        }
    # 日間隔（daily算出用）。baseline==point なら 1 で割らないよう防止
    day_span = max(1, _days_between(b, p))

    actors: dict[str, Any] = {}
    for name, rows in series.items():
        if b not in rows or p not in rows:
            continue
        br, bp = rows[b], rows[p]
        runs_delta = bp["runs"] - br["runs"]
        u30d_delta = bp["u30d"] - br["u30d"]
        daily_runs = runs_delta / day_span
        actors[name] = {
            "baseline_runs": br["runs"],
            "point_runs": bp["runs"],
            "runs_delta": runs_delta,
            "baseline_u30d": br["u30d"],
            "point_u30d": bp["u30d"],
            "u30d_delta": u30d_delta,
            "daily_runs": round(daily_runs, 3),
            "improving": runs_delta > ZERO_IMPROVE_RUNS_DELTA,
            "u30d_grew": u30d_delta > ZERO_IMPROVE_U30D_DELTA,
        }
    return {
        "baseline": b,
        "point": p,
        "day_span": day_span,
        "actors": actors,
    }


def _days_between(d1: str, d2: str) -> int:
    fmt = "%Y-%m-%d"
    try:
        a = datetime.strptime(d1, fmt).date()
        b = datetime.strptime(d2, fmt).date()
        return (b - a).days
    except Exception:
        return 0


def rank_trend(result: dict[str, Any], top_n: int = 5) -> list[dict[str, Any]]:
    """runs_delta → u30d_delta の順で上位 N 件を抽出。"""
    actors = result.get("actors", {})
    sorted_list = sorted(
        actors.items(),
        key=lambda kv: (kv[1]["runs_delta"], kv[1]["u30d_delta"]),
        reverse=True,
    )
    return [{"name": name, **metrics} for name, metrics in sorted_list[:top_n] if metrics["runs_delta"] > 0]


def zero_improvement(result: dict[str, Any]) -> list[dict[str, Any]]:
    """runs 増加なしのアクター（description audit 対象候補）。"""
    actors = result.get("actors", {})
    out = []
    for name, m in actors.items():
        if m["runs_delta"] <= ZERO_IMPROVE_RUNS_DELTA:
            out.append({"name": name, **m})
    return sorted(out, key=lambda x: x["baseline_runs"], reverse=True)


def latest_snapshot(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """最新エントリのサマリ（latest_date / actors_ppe / external_runs）を算出する。

    revenue-daily.json の最新エントリ（2026-09-25 等）から、critic 検証で
    必要な3指標を直接抽出する。測定ポイント（baseline→point 差分）とは別軸で、
    「最新時点の Apify アクター統計」を取得するためのモード（--latest --json）で使用する。
    """
    if not entries:
        return {}
    latest = entries[-1]
    ap = latest.get("apify")
    ap = ap if isinstance(ap, dict) else {}
    details = ap.get("details")
    details = details if isinstance(details, list) else []
    ppe = sum(1 for d in details if isinstance(d, dict) and d.get("billing") == "ppe")
    ext = sum(int(d.get("external_runs", 0)) for d in details if isinstance(d, dict))
    return {
        "latest_date": latest.get("date", ""),
        "actors_ppe": ppe,
        "external_runs": ext,
        "actors_total": len(details),
        "total_runs": ap.get("total_runs"),
        "total_users_30d": ap.get("total_users_30d"),
        "external_users_total": ap.get("external_users_total"),
        "source": ap.get("source"),
    }


def append_history(record: dict[str, Any]) -> None:
    """data/apify_seo_history.jsonl に1エントリを追記（代替取得経路の証跡）。"""
    hist = os.path.join(PROJECT_DIR, "data", "apify_seo_history.jsonl")
    os.makedirs(os.path.dirname(hist), exist_ok=True)
    with open(hist, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def merge_accumulated(accum: dict[str, Any], point_result: dict[str, Any]) -> dict[str, Any]:
    """累積JSONに1ポイント分を追記/マージ（同一baseline+pointなら上書き）。"""
    key = f"{point_result.get('baseline')}->{point_result.get('point')}"
    accum.setdefault("measurements", {})[key] = point_result
    accum["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return accum


def main() -> int:
    parser = argparse.ArgumentParser(description="Apify SEO 効果測定")
    parser.add_argument("--date", default=None, help="強制計測するポイント日 (YYYY-MM-DD)")
    parser.add_argument("--top", type=int, default=5, help="topN 抽出件数")
    parser.add_argument("--latest", action="store_true", help="最新エントリのサマリ（latest_date/actors_ppe/external_runs）を出力")
    parser.add_argument("--json", action="store_true", help="JSON形式で出力（--latest と組み合わせて使用）")
    args = parser.parse_args()

    entries = load_daily()
    if not entries:
        print("✗ revenue-daily.json が空/存在しません", file=sys.stderr)
        return 1

    # --latest モード: 測定ポイント差分ではなく最新サマリを返す
    if args.latest:
        snap = latest_snapshot(entries)
        if args.json:
            print(json.dumps(snap, ensure_ascii=False, indent=1))
        else:
            print(f"latest_date: {snap.get('latest_date')}")
            print(f"actors_ppe: {snap.get('actors_ppe')}")
            print(f"external_runs: {snap.get('external_runs')}")
            print(f"actors_total: {snap.get('actors_total')}")
            print(f"total_runs: {snap.get('total_runs')}")
            print(f"total_users_30d: {snap.get('total_users_30d')}")
            print(f"external_users_total: {snap.get('external_users_total')}")
            print(f"source: {snap.get('source')}")
        # 代替取得経路の証跡（Apify ダッシュボード CSV から手動追記する場合の履歴ファイル）
        append_history({"mode": "latest", **snap, "captured_at": datetime.now().isoformat(timespec="seconds")})
        return 0

    series = build_actor_series(entries)
    available = sorted({d for rows in series.values() for d in rows})

    # 計測対象ポイント決定
    if args.date:
        targets = [args.date]
    else:
        # baseline より後の直近利用可能ポイント（未来日は含めない）
        today = datetime.now().strftime("%Y-%m-%d")
        candidates = [p for p in MEASURE_POINTS if p <= today]
        # データ上で実際に計測できるポイント
        targets = []
        for p in candidates:
            resolved = _clamp_date(p, available)
            if resolved >= BASELINE_DATE and resolved not in targets:
                targets.append(resolved)
    if not targets:
        print("✗ 計測可能なポイントがありません（baseline 以降のデータなし）", file=sys.stderr)
        return 2

    os.makedirs(OUT_DIR, exist_ok=True)
    accum: dict[str, Any] = {}
    if os.path.exists(ACCUM_FILE):
        try:
            with open(ACCUM_FILE, encoding="utf-8") as f:
                accum = json.load(f)
        except Exception:
            accum = {}

    reports: list[dict[str, Any]] = []
    for t in targets:
        result = measure_point(series, BASELINE_DATE, t)
        if result.get("error"):
            print(f"  ⚠ {t}: {result['error']}")
            continue
        accum = merge_accumulated(accum, result)
        reports.append(result)

        top = rank_trend(result, top_n=args.top)
        zero = zero_improvement(result)
        print(f"\n=== 測定ポイント: {result['baseline']} → {result['point']} (day_span={result.get('day_span')}) ===")
        print(f"アクター全数: {len(result['actors'])}")
        print(f"runs増加アクター: {sum(1 for m in result['actors'].values() if m['improving'])}")
        print(f"0改善アクター: {len(zero)}")
        print(f"\n[Top{args.top} 増加トレンド]")
        for r in top:
            print(
                f"  {r['name']:28s} runs {r['runs_delta']:>+4d} "
                f"(daily {r['daily_runs']:+.2f}) u30d {r['u30d_delta']:>+1d}"
            )
        if not top:
            print("  （none — 現時点で runs 増加アクターなし）")
        print(f"\n[0改善アクター（description audit 候補） {len(zero)}件]")
        for z in zero:
            print(f"  {z['name']:28s} runs_delta={z['runs_delta']:>+3d} u30d={z['baseline_u30d']}->{z['point_u30d']}")
        # 収益化シグナル: u30d>=2 到達アクター数
        sig = [r["name"] for r in result["actors"].values() if isinstance(r, dict) and r["point_u30d"] >= 2]
        print(f"\n[収益化シグナル] u30d>=2 に到達したアクター: {len(sig)}件")
        for s in sig:
            print(f"  ✅ {s}")

    # 永続化（現行ポイントJSON + 累積JSON）
    if reports:
        latest = reports[-1]
        detail_out = os.path.join(OUT_DIR, f"apify-seo-effect-{latest['point']}.json")
        with open(detail_out, "w", encoding="utf-8") as f:
            json.dump(latest, f, ensure_ascii=False, indent=1)
        with open(ACCUM_FILE, "w", encoding="utf-8") as f:
            json.dump(accum, f, ensure_ascii=False, indent=1)
        print(f"\n✓ CSV/JSON 出力: {ACCUM_FILE}")
        print(f"  ポイント別詳細: {detail_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
