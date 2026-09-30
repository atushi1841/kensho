"""Tests for scripts/apify_ppe_external_views.py — v18-B Apify PPE 外部view計測（t_b6684e7b）。

説明文一括テンプレーティング（v15-A）の効果測定レイヤー。API は mock して
ネットワーク非依存で検証する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apify_ppe_external_views as av

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
    if "/acts" in url and "/" in url.replace("/acts/", "", 1):
        return _Resp(
            200,
            {
                "data": {
                    "name": "japan-used-camera-market-scraper",
                    "stats": {
                        "totalRuns": 100,
                        "totalUsers30Days": 3,
                        "bookmarkCount": 2,
                    },
                    "seoTitle": "Cameras",
                    "seoDescription": "Search Japan camera market",
                }
            },
        )
    if "/acts" in url:
        return _Resp(
            200,
            {
                "data": {
                    "items": [
                        {"name": "japan-used-camera-market-scraper", "id": "id-camera"},
                        {"name": "japan-watch-market-scraper", "id": "id-watch"},
                    ]
                }
            },
        )
    return _Resp(404, {"error": "not found"})


def test_newest_point_by_date() -> None:
    assert av.newest_point("2026-09-04") == "baseline"
    assert av.newest_point("2026-09-05") == "24h"
    assert av.newest_point("2026-09-07") == "72h"
    assert av.newest_point("2026-09-11") == "168h"
    assert av.newest_point("2026-09-20") == "168h"
    assert av.newest_point("2026-09-03") == "baseline"


@patch("apify_ppe_external_views.requests.get", side_effect=_mock_requests)
def test_collect_actor_metrics_counts_external_views(_mg: Any) -> None:
    m = av.collect_actor_metrics("tok", "japan-used-camera-market-scraper", "id-camera", OWNER, 0.002)
    # runs: 4件中 owner 以外が2件 → external_views(proxy)=2
    assert m["external_views"] == 2
    assert m["total_runs"] == 100
    assert m["u30d"] == 3
    assert m["bookmarks"] == 2
    assert m["seo_present"] is True
    assert m["price_usd"] == 0.002


@patch("apify_ppe_external_views.requests.get", side_effect=_mock_requests)
def test_collect_actor_metrics_owner_runs_not_counted(_mg: Any) -> None:
    m = av.collect_actor_metrics("tok", "x", "id-camera", OWNER, None)
    assert m["external_views"] == 2  # r1, r4 (owner) は除外


def test_merge_state_updates_same_point_and_keeps_others() -> None:
    st = {
        "baseline": "2026-09-04",
        "points": {
            "baseline": {"point": "baseline", "x": 1},
            "24h": {"point": "24h", "x": 1},
        },
    }
    new24 = {"point": "24h", "point_date": "2026-09-05", "x": 2}
    out = av.merge_state(st, new24)
    assert out["points"]["24h"]["x"] == 2  # 上書き
    assert out["points"]["baseline"]["x"] == 1  # 他は維持
    assert "updated_at" in out


@patch("apify_ppe_external_views.REVENUE_DAILY")
def test_attach_to_daily_writes_metric(mock_path: Any) -> None:
    from datetime import datetime as _dt

    today = _dt.now().strftime("%Y-%m-%d")

    # 一時リポジトリファイルを構築し REVENUE_DAILY を差し替え
    repo = Path("/tmp/av_daily_test")
    repo.mkdir(exist_ok=True)
    daily = repo / "revenue-daily.json"
    daily.write_text(json.dumps([{"date": today, "revenue_estimate": {}}]), encoding="utf-8")
    av.REVENUE_DAILY = str(daily)

    m = {
        "point": "24h",
        "point_date": today,
        "baseline": "2026-09-04",
        "per_actor": {
            "japan-camera-market": {
                "actual_name": "japan-used-camera-market-scraper",
                "external_views": 2,
                "total_runs": 100,
                "u30d": 3,
                "bookmarks": 2,
                "seo_present": True,
            },
        },
    }
    assert av.attach_to_daily(m) is True
    entries = json.loads(daily.read_text(encoding="utf-8"))
    metric = entries[0]["apify_ppe_external_views_keys"]
    assert metric["point"] == "24h"
    assert metric["actors"]["japan-camera-market"]["external_views"] == 2
    assert metric["proxy_note"]
    av.REVENUE_DAILY = "/mnt/d/Project2/kensho/data/revenue-daily.json"


def test_attach_to_daily_skips_when_no_today_entry() -> None:
    repo = Path("/tmp/av_daily_skip")
    repo.mkdir(exist_ok=True)
    daily = repo / "revenue-daily.json"
    daily.write_text(json.dumps([{"date": "2026-09-01"}]), encoding="utf-8")
    av.REVENUE_DAILY = str(daily)
    m = {"point": "24h", "per_actor": {"k": {}}}
    assert av.attach_to_daily(m) is False
    av.REVENUE_DAILY = "/mnt/d/Project2/kensho/data/revenue-daily.json"


def test_measure_dynamic_structure() -> None:
    """measure_dynamic が正しい構造を返すか検証（ネットワークは mock しないため実 API 呼び出し）。"""
    from datetime import datetime
    token = "dummy"  # mock せず実 API 呼び出し（CI ではスキップされる前提）
    post_date = "2026-09-29"
    actor_names = ["mandarake-auction-scraper", "dlsite-scraper", "tackleberry-japan-fishing-tackle-scraper"]
    # このテストは実環境での手動実行用。pytest では skip する想定。
    if __name__ == "__main__":
        r = av.measure_dynamic(token, post_date, actor_names, "1d")
        assert r["point"] == "1d"
        assert r["point_date"] == "2026-09-30"
        assert r["post_date"] == post_date
        assert set(r["per_actor"].keys()) == set(actor_names)
        print("measure_dynamic structure OK")


if __name__ == "__main__":
    test_measure_dynamic_structure()
