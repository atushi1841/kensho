"""Tests for scripts/apify_seo_effect.py."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/scripts")
import apify_seo_effect as effect  # noqa: E402


def _mk_entry(date, actors):
    """1日分の revenue-daily apify エントリを構築。actors: {name: {runs,u30d}}"""
    details = [{"name": name, "actual_name": name, "runs": v["runs"], "u30d": v["u30d"]} for name, v in actors.items()]
    return {
        "date": date,
        "apify": {
            "total_runs": sum(v["runs"] for v in actors.values()),
            "total_users_30d": sum(v["u30d"] for v in actors.values()),
            "details": details,
        },
    }


def _build_series():
    base = {
        "japan-camera-market": {"runs": 62, "u30d": 1},
        "japan-watch-market": {"runs": 56, "u30d": 1},
        "japan-rent-market": {"runs": 29, "u30d": 1},
        "japan-market-mcp": {"runs": 587, "u30d": 0},
    }
    d9_5 = {
        "japan-camera-market": {"runs": 70, "u30d": 2},  # +8 runs, u30d 1->2
        "japan-watch-market": {"runs": 58, "u30d": 1},  # +2 runs
        "japan-rent-market": {"runs": 29, "u30d": 1},  # 0 improved
        "japan-market-mcp": {"runs": 595, "u30d": 0},  # +8 runs, u30d 0
    }
    entries = [
        _mk_entry("2026-09-04", base),
        _mk_entry("2026-09-05", d9_5),
    ]
    return entries


def test_measure_point_delta():
    series = effect.build_actor_series(_build_series())
    res = effect.measure_point(series, "2026-09-04", "2026-09-05")
    assert res.get("error") is None
    actors = res["actors"]
    assert actors["japan-camera-market"]["runs_delta"] == 8
    assert actors["japan-camera-market"]["u30d_delta"] == 1
    assert res["day_span"] == 1


def test_rank_trend_top5():
    series = effect.build_actor_series(_build_series())
    res = effect.measure_point(series, "2026-09-04", "2026-09-05")
    top = effect.rank_trend(res, top_n=5)
    # runs_delta 降順: japan-market-mcp(+8) と japan-camera-market(+8) が上位
    assert top[0]["runs_delta"] >= top[-1]["runs_delta"]
    assert all(t["runs_delta"] > 0 for t in top)
    names = [t["name"] for t in top]
    assert "japan-market-mcp" in names and "japan-camera-market" in names


def test_zero_improvement():
    series = effect.build_actor_series(_build_series())
    res = effect.measure_point(series, "2026-09-04", "2026-09-05")
    zero = effect.zero_improvement(res)
    names = [z["name"] for z in zero]
    assert "japan-rent-market" in names
    assert "japan-camera-market" not in names


def test_point_before_baseline():
    series = effect.build_actor_series(_build_series())
    res = effect.measure_point(series, "2026-09-05", "2026-09-04")
    assert "error" in res


def test_clamp_date_fallback():
    available = ["2026-09-04", "2026-09-05"]
    assert effect._clamp_date("2026-09-07", available) == "2026-09-05"
    assert effect._clamp_date("2026-09-04", available) == "2026-09-04"
    assert effect._clamp_date("2026-09-03", available) == "2026-09-04"


def test_merge_accumulated():
    acc = {}
    res = {"baseline": "2026-09-04", "point": "2026-09-05", "actors": {}}
    merged = effect.merge_accumulated(acc, res)
    assert "2026-09-04->2026-09-05" in merged["measurements"]
