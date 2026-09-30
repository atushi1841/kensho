"""Tests for scripts/apify_post_promo_tracker.py — 投稿起点の動的 external_views 追跡."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apify_post_promo_tracker as apt

OWNER = "owner-id-123"


class _Resp:
    def __init__(self, status: int, payload: Any) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def _mock_requests(url: str, *args: Any, **kwargs: Any) -> _Resp:
    """URL に応じた固定レスポンスを返す requests.get のフェイク。"""
    if "/users/me" in url:
        return _Resp(200, {"data": {"id": OWNER}})
    if "/runs" in url:
        runs = [
            {"userId": OWNER, "id": "r1"},
            {"userId": "ext-user-alpha", "id": "r2"},
            {"userId": "ext-user-beta", "id": "r3"},
            {"userId": OWNER, "id": "r4"},
        ]
        return _Resp(200, {"data": {"items": runs}})
    if "/acts" in url and "/acts/" in url and url.count("/") >= 4:
        # /acts/{actor_id} - actor detail
        return _Resp(
            200,
            {
                "data": {
                    "name": "mandarake-auction-scraper",
                    "stats": {
                        "totalRuns": 100,
                        "totalUsers30Days": 3,
                        "bookmarkCount": 2,
                    },
                }
            },
        )
    if "/acts" in url:
        # /acts?my=true - list my actors
        return _Resp(
            200,
            {
                "data": {
                    "items": [
                        {"name": "mandarake-auction-scraper", "id": "id-mandarake"},
                        {"name": "dlsite-scraper", "id": "id-dlsite"},
                        {"name": "tackleberry-japan-fishing-tackle-scraper", "id": "id-tackleberry"},
                    ]
                }
            },
        )
    return _Resp(404, {"error": "not found"})


def test_compute_measure_points() -> None:
    """投稿日から動的計測ポイントが正しく計算されるか。"""
    points = apt.compute_measure_points("2026-09-29")
    assert points["1d"] == "2026-09-30"
    assert points["3d"] == "2026-10-02"
    assert points["7d"] == "2026-10-06"

    points2 = apt.compute_measure_points("2026-12-31")
    assert points2["1d"] == "2027-01-01"
    assert points2["3d"] == "2027-01-03"
    assert points2["7d"] == "2027-01-07"


def test_newest_point_by_date() -> None:
    """今日時点で計測可能な最新ポイントが正しく返されるか。"""
    measure_points = {"1d": "2026-09-30", "3d": "2026-10-02", "7d": "2026-10-06"}

    assert apt.newest_point(measure_points, today="2026-09-29") is None  # 全て未来
    assert apt.newest_point(measure_points, today="2026-09-30") == "1d"
    assert apt.newest_point(measure_points, today="2026-10-01") == "1d"
    assert apt.newest_point(measure_points, today="2026-10-02") == "3d"
    assert apt.newest_point(measure_points, today="2026-10-05") == "3d"
    assert apt.newest_point(measure_points, today="2026-10-06") == "7d"
    assert apt.newest_point(measure_points, today="2026-10-10") == "7d"


@patch("apify_post_promo_tracker.requests.get", side_effect=_mock_requests)
def test_collect_actor_metrics_counts_external_views(_mg: Any) -> None:
    """外部 run（owner 以外）のみが external_views としてカウントされるか。"""
    m = apt.collect_actor_metrics("tok", "mandarake-auction-scraper", "id-mandarake", OWNER)
    # runs: 4件中 owner 以外が2件 (r2, r3) → external_views=2
    assert m["external_views"] == 2
    assert m["total_runs"] == 100
    assert m["u30d"] == 3
    assert m["bookmarks"] == 2


@patch("apify_post_promo_tracker.requests.get", side_effect=_mock_requests)
def test_measure_returns_expected_structure(_mg: Any) -> None:
    """measure() が期待通りの構造を返すか。"""
    measure_points = {"1d": "2026-09-30", "3d": "2026-10-02", "7d": "2026-10-06"}
    actor_names = ["mandarake-auction-scraper", "dlsite-scraper", "tackleberry-japan-fishing-tackle-scraper"]

    result = apt.measure("tok", "1d", measure_points, actor_names, "2026-09-29")

    assert result["point"] == "1d"
    assert result["point_date"] == "2026-09-30"
    assert result["post_date"] == "2026-09-29"
    assert "measured_at" in result
    assert "per_actor" in result
    assert set(result["per_actor"].keys()) == set(actor_names)


def test_merge_state_updates_same_point_and_keeps_others() -> None:
    """同一ポイントは上書き、それ以外は維持されるか。"""
    state = {
        "post_date": "2026-09-29",
        "points": {
            "1d": {"point": "1d", "x": 1},
            "3d": {"point": "3d", "x": 1},
        },
    }
    new1d = {"point": "1d", "point_date": "2026-09-30", "x": 2, "post_date": "2026-09-29"}
    out = apt.merge_state(state, new1d)
    assert out["points"]["1d"]["x"] == 2  # 上書き
    assert out["points"]["3d"]["x"] == 1  # 他は維持
    assert "updated_at" in out


def test_attach_to_daily_writes_metric() -> None:
    """revenue-daily.json の当日エントリに metric が追記されるか。"""
    import tempfile
    from datetime import datetime, UTC

    with tempfile.TemporaryDirectory() as tmp:
        daily = Path(tmp) / "revenue-daily.json"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        daily.write_text(json.dumps([{"date": today, "revenue_estimate": {}}]), encoding="utf-8")

        # モジュール変数を一時的に差し替え
        original = apt.REVENUE_DAILY
        apt.REVENUE_DAILY = str(daily)

        m = {
            "point": "1d",
            "point_date": today,
            "post_date": "2026-09-29",
            "measured_at": "2026-09-29T12:00:00+00:00",
            "per_actor": {
                "mandarake-auction-scraper": {
                    "actual_name": "mandarake-auction-scraper",
                    "external_views": 2,
                    "total_runs": 100,
                    "u30d": 3,
                    "bookmarks": 2,
                }
            },
        }
        assert apt.attach_to_daily(m) is True
        entries = json.loads(daily.read_text(encoding="utf-8"))
        metric = entries[0]["apify_post_promo_tracker"]
        assert metric["point"] == "1d"
        assert metric["actors"]["mandarake-auction-scraper"]["external_views"] == 2
        assert metric["proxy_note"]

        apt.REVENUE_DAILY = original


def test_attach_to_daily_skips_when_no_today_entry() -> None:
    """当日エントリがない場合は False を返し書き込まないか。"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        daily = Path(tmp) / "revenue-daily.json"
        daily.write_text(json.dumps([{"date": "2026-09-01"}]), encoding="utf-8")

        original = apt.REVENUE_DAILY
        apt.REVENUE_DAILY = str(daily)

        m = {"point": "1d", "per_actor": {"k": {}}}
        assert apt.attach_to_daily(m) is False

        apt.REVENUE_DAILY = original


if __name__ == "__main__":
    test_compute_measure_points()
    test_newest_point_by_date()
    test_collect_actor_metrics_counts_external_views()
    test_measure_returns_expected_structure()
    test_merge_state_updates_same_point_and_keeps_others()
    test_attach_to_daily_writes_metric()
    test_attach_to_daily_skips_when_no_today_entry()
    print("All tests passed!")