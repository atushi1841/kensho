"""
Tests for scripts/apify_seo_audit.py — Apify Store SEO監査（t_ce1f9b36 / critic v13-A）

ネットワーク不使用: fixtureベースの競合データで analyze_actor を検証する。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apify_seo_audit as seo


def _actor(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "japan-used-camera-market-scraper",
        "title": "Japan Used Camera Market — Cross-Shop Price Comparison",
        "description": "Scrape used camera prices from Japanese shops MAPS Camera and Kitahara.",
        "seoTitle": "Japan Used Camera Market Price API",
        "seoDescription": "Compare used camera prices across Japanese shops.",
        "categories": ["ECOMMERCE"],
        "readmeSummary": "This actor scrapes Japanese used camera market prices. "
        "It returns structured JSON with shop name, price and condition. "
        "Use it for resale arbitrage research and market analysis dashboards "
        "with weekly refreshed data for the whole catalog of listings.",
        "isPublic": True,
        "stats": {"totalUsers30Days": 1, "totalRuns": 60},
    }
    base.update(overrides)
    return base


def _comp(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "competitor-actor",
        "username": "someoneelse",
        "title": "Camera Price Tracker — Mercari Yahoo Auctions Sold Listings Monitor",
        "description": "Track camera sold listings on Mercari and Yahoo Auctions with "
        "median sold price, hammer price and condition data for resale research.",
        "categories": ["ECOMMERCE", "AUTOMATION", "DEVELOPER_TOOLS"],
        "stats": {"totalUsers30Days": 12},
    }
    base.update(overrides)
    return base


# --- build_search_query ---


def test_build_search_query_stops_generics() -> None:
    actor = _actor(title="Japan Used Camera Market Scraper")
    query = seo.build_search_query(actor)
    lowered = query.lower()
    assert "camera" in lowered
    for stop in ("japan", "used", "market", "scraper"):
        assert stop not in lowered


def test_build_search_query_falls_back_to_name() -> None:
    actor = _actor(title="API Data", seoTitle="", name="kakaku-price-search")
    query = seo.build_search_query(actor)
    assert "kakaku" in query


def test_build_search_queries_orders_narrow_to_wide() -> None:
    actor = _actor(
        seoTitle="",
        title="Japan Used Camera Market — Cross Shop Price Comparison",
        name="japan-used-camera-market-scraper",
        description="Scrape used camera prices from MAPS Camera and Kitahara shops.",
    )
    queries = seo.build_search_queries(actor)
    assert queries, "クエリ候補が最低1件必要"
    # 狭い（語数多い）→ 広い（1語）の順
    assert len(queries[0].split()) >= 2
    assert queries[-1] in [q for q in queries]
    assert len(queries[-1].split()) == 1
    # ハイフン連結語（cross-shop）がそのまま検索語にならない
    assert all("cross-shop" not in q for q in queries)
    # 重複なし
    assert len(queries) == len(set(queries))


def test_fetch_competitors_multi_tries_next_query() -> None:
    calls: list[str] = []

    def fake_fetch(url: str, timeout: int = 30) -> dict[str, Any]:
        calls.append(url)
        if "camera%20mercari" in url:
            return {"data": {"items": []}}
        return {
            "data": {
                "items": [
                    {
                        "username": "other",
                        "name": "rival",
                        "title": "Mercari Camera Sold Price Tracker",
                        "description": "mercari camera sold price data export",
                        "stats": {},
                    }
                ]
            }
        }

    original = seo.fetch_json
    seo.fetch_json = fake_fetch  # type: ignore[assignment]
    try:
        comps, used = seo.fetch_competitors_multi(
            "tok", _actor(), ["camera mercari", "mercari"], 5, set(), sleep_seconds=0
        )
    finally:
        seo.fetch_json = original  # type: ignore[assignment]
    assert [c["name"] for c in comps] == ["rival"]
    assert used == "mercari"
    assert len(calls) == 2


def test_fetch_competitors_multi_exhausted_returns_best() -> None:
    def fake_fetch(url: str, timeout: int = 30) -> dict[str, Any]:
        return {"data": {"items": []}}

    original = seo.fetch_json
    seo.fetch_json = fake_fetch  # type: ignore[assignment]
    try:
        comps, used = seo.fetch_competitors_multi("tok", _actor(), ["aaa bbb", "aaa"], 5, set(), sleep_seconds=0)
    finally:
        seo.fetch_json = original  # type: ignore[assignment]
    assert comps == []
    assert used == "aaa bbb"


def test_fetch_competitors_multi_drops_irrelevant_actor() -> None:
    """人気順上位が無関係アクターなら競合0件として扱う（ノイズ提案防止）。"""

    def fake_fetch(url: str, timeout: int = 30) -> dict[str, Any]:
        return {
            "data": {
                "items": [
                    {
                        "username": "other",
                        "name": "youtube-scraper",
                        "title": "YouTube Scraper",
                        "description": "Extract video transcripts channel subscribers",
                        "stats": {},
                    }
                ]
            }
        }

    original = seo.fetch_json
    seo.fetch_json = fake_fetch  # type: ignore[assignment]
    try:
        comps, used = seo.fetch_competitors_multi("tok", _actor(), ["camera"], 5, set(), sleep_seconds=0)
    finally:
        seo.fetch_json = original  # type: ignore[assignment]
    assert comps == []
    assert used == "camera"


# --- analyze_actor: 検出ロジック ---


def test_filter_competitors_removes_irrelevant() -> None:
    actor = _actor()
    relevant = _comp(
        title="Camera Price Tracker",
        description="camera lens market price comparison data",
    )
    irrelevant = _comp(
        name="youtube-scraper",
        title="YouTube Scraper",
        description="Extract video transcripts channel subscribers comments",
    )
    kept = seo.filter_competitors(actor, [irrelevant, relevant])
    assert [c["name"] for c in kept] == ["competitor-actor"]
    # 全滅なら空（呼び出し側が no_competitor_data として扱う）
    assert seo.filter_competitors(actor, [irrelevant]) == []


def test_missing_keywords_ignores_connectors() -> None:
    actor = _actor(description="Scrape prices.", title="Camera Market", seoTitle="")
    comps = [
        _comp(description="comprehensive details across other more runs via google"),
        _comp(description="comprehensive details across other more runs via google"),
    ]
    kw = next(
        (f for f in seo.analyze_actor(actor, comps) if f["issue"] == "missing_keywords"),
        None,
    )
    assert kw is None or not any(bad in kw["current"] for bad in ("comprehensive", "other", "more", "via"))


def test_detects_short_description() -> None:
    actor = _actor(description="Short desc.")
    comps = [_comp(description="x" * 200), _comp(description="y" * 220)]
    issues = {f["issue"] for f in seo.analyze_actor(actor, comps)}
    assert "short_description" in issues


def test_detects_missing_keywords() -> None:
    actor = _actor()
    comps = [
        _comp(
            title="Sold Camera Mercari Tracker",
            description="mercari sold camera hammer price data",
        ),
        _comp(
            name="c2",
            title="Sold Camera Mercari Monitor",
            description="mercari sold camera listings export",
        ),
    ]
    findings = seo.analyze_actor(actor, comps)
    kw = next((f for f in findings if f["issue"] == "missing_keywords"), None)
    assert kw is not None
    assert "mercari" in kw["current"]


def test_detects_missing_categories() -> None:
    actor = _actor(categories=["ECOMMERCE"])
    comps = [
        _comp(categories=["ECOMMERCE", "AUTOMATION"]),
        _comp(categories=["ECOMMERCE", "AUTOMATION"]),
    ]
    issues = {f["issue"] for f in seo.analyze_actor(actor, comps)}
    assert "missing_categories" in issues


def test_detects_discovery_gap() -> None:
    actor = _actor(stats={"totalUsers30Days": 0, "totalRuns": 5})
    comps = [
        _comp(stats={"totalUsers30Days": 3}),
        _comp(stats={"totalUsers30Days": 5}),
    ]
    findings = seo.analyze_actor(actor, comps)
    gap = next((f for f in findings if f["issue"] == "discovery_gap"), None)
    assert gap is not None
    assert gap["current"] == "0"


def test_no_discovery_gap_when_we_have_users() -> None:
    actor = _actor(stats={"totalUsers30Days": 4, "totalRuns": 60})
    comps = [
        _comp(stats={"totalUsers30Days": 3}),
        _comp(stats={"totalUsers30Days": 5}),
    ]
    issues = {f["issue"] for f in seo.analyze_actor(actor, comps)}
    assert "discovery_gap" not in issues


def test_detects_missing_seo_fields() -> None:
    actor = _actor(seoTitle="", seoDescription="", readmeSummary="tiny")
    comps = [_comp(), _comp(name="c2")]
    issues = {f["issue"] for f in seo.analyze_actor(actor, comps)}
    assert {"seo_title_missing", "seo_description_missing", "thin_readme"} <= issues


def test_title_too_long_detected() -> None:
    actor = _actor(title=("Japan Camera Market Price Comparison Tool Extended " * 3).strip())
    comps = [_comp(), _comp(name="c2")]
    issues = {f["issue"] for f in seo.analyze_actor(actor, comps)}
    assert "title_too_long" in issues


def test_no_competitors_yields_marker() -> None:
    findings = seo.analyze_actor(_actor(), [])
    assert findings[0]["issue"] == "no_competitor_data"


# --- summarize / write_csv ---


def test_summarize_counts() -> None:
    rows = [
        {"actor": "a", "issue": "short_description"},
        {"actor": "a", "issue": "missing_categories"},
        {"actor": "b", "issue": "short_description"},
    ]
    s = seo.summarize(rows)
    assert s["total_findings"] == 3
    assert s["actors_with_findings"] == 2
    assert s["by_issue"]["short_description"] == 2
    assert s["worst_actors"][0][0] == "a"


def test_write_csv(tmp_path: Path) -> None:
    out = tmp_path / "diff.csv"
    rows = [
        {
            "actor": "x",
            "issue": "short_description",
            "field": "description",
            "current": "10字",
            "suggested": "拡張",
            "evidence": "中央値=180",
            "search_query": "camera mercari",
            "competitors": 5,
        }
    ]
    seo.write_csv(rows, str(out))
    with open(out, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        loaded = list(reader)
    assert len(loaded) == 1
    assert loaded[0]["actor"] == "x"
    assert loaded[0]["issue"] == "short_description"


# --- fixture経由のエンドツーエンド（ネットワーク不使用） ---


def test_main_with_fixture(tmp_path: Path, capsys: Any) -> None:
    fixture = {
        "actors": [
            _actor(description="Tiny.", categories=["ECOMMERCE"]),
        ],
        "competitors": {
            "japan-used-camera-market-scraper": [
                _comp(),
                _comp(name="c2", stats={"totalUsers30Days": 9}),
            ]
        },
    }
    fx = tmp_path / "fx.json"
    fx.write_text(json.dumps(fixture), encoding="utf-8")
    json_out = tmp_path / "out.json"
    csv_out = tmp_path / "out.csv"
    rc = seo.main([
        "--fixture",
        str(fx),
        "--json",
        str(json_out),
        "--csv",
        str(csv_out),
        "--quiet",
    ])
    assert rc == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["actors_audited"] == 1
    assert payload["summary"]["total_findings"] >= 1
    issues = {f["issue"] for f in payload["findings"]}
    assert "short_description" in issues
    assert csv_out.exists()


def test_fetch_competitors_excludes_own_username() -> None:
    captured: dict[str, Any] = {}

    def fake_fetch(url: str, timeout: int = 30) -> dict[str, Any]:
        captured["url"] = url
        return {
            "data": {
                "items": [
                    {"username": seo.OWN_USERNAME, "name": "mine"},
                    {"username": "other", "name": "rival", "stats": {}},
                ]
            }
        }

    original = seo.fetch_json
    seo.fetch_json = fake_fetch  # type: ignore[assignment]
    try:
        comps = seo.fetch_competitors("tok", "camera mercari", 5, {"mine"})
    finally:
        seo.fetch_json = original  # type: ignore[assignment]
    assert [c["name"] for c in comps] == ["rival"]
    assert "sortBy=popularity" in captured["url"]
