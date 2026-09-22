"""Tests for the TCG price-trend query engine (scripts/tcg_price_query.py)."""
import json

from scripts.tcg_price_query import (
    build_series,
    current_price,
    load_observations,
    price_history,
    top_movers,
)


def _obs(name, url, used, collected_at, **kw):
    rec = {
        "source": "suruga-ya.jp", "keyword": "kw-test", "name": name, "url": url,
        "used_price_jpy": used, "new_price_jpy": None, "list_price_jpy": None,
        "marketplace_price_jpy": None, "brand": "", "condition_badge": "",
        "release_date": "", "in_stock": True, "image_url": "",
        "collected_at": collected_at,
    }
    rec.update(kw)
    return rec


def sample_obs():
    return [
        _obs("リザードン SR", "https://s.example/p/d001", 10000, "2026-09-21T09:00:00Z"),
        _obs("リザードン SR", "https://s.example/p/d001", 12000, "2026-09-22T09:00:00Z"),
        _obs("ピカチュウ レア", "https://s.example/p/d002", 800, "2026-09-21T09:00:00Z"),
        _obs("ピカチュウ レア", "https://s.example/p/d002", 700, "2026-09-22T09:00:00Z"),
        _obs("無変化カード", "https://s.example/p/d003", 500, "2026-09-21T09:00:00Z"),
        _obs("無変化カード", "https://s.example/p/d003", 500, "2026-09-22T09:00:00Z"),
    ]


def test_load_observations_roundtrip(tmp_path):
    p = tmp_path / "accumulated.jsonl"
    rows = [_obs("a", "u1", 100, "2026-09-21T00:00:00Z")]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    loaded = load_observations(p)
    assert len(loaded) == 1
    assert loaded[0]["name"] == "a"


def test_build_series_groups_by_url():
    obs = [
        _obs("a", "u1", 100, "2026-09-21T00:00:00Z"),
        _obs("a", "u1", 150, "2026-09-22T00:00:00Z"),
        _obs("b", "u2", 50, "2026-09-21T00:00:00Z"),
    ]
    series = build_series(obs)
    assert len(series) == 2
    assert len(series["u1"].observations) == 2


def test_current_price_latest():
    obs = sample_obs()
    r = current_price(obs, "リザードン")
    assert r["found"] is True
    assert r["used_price_jpy"] == 12000  # latest observation


def test_current_price_no_match():
    r = current_price(sample_obs(), "見つからないカード")
    assert r["found"] is False


def test_price_history_oldest_first():
    r = price_history(sample_obs(), "ピカチュウ")
    assert r["found"] is True
    prices = [h["used_price_jpy"] for h in r["history"]]
    assert prices == [800, 700]


def test_top_movers_ranked():
    r = top_movers(sample_obs(), limit=10)
    assert r["mover_count"] == 2  # 500→500 has no delta
    assert r["movers"][0]["name"] == "リザードン SR"
    assert r["movers"][0]["delta_jpy"] == 2000


def test_top_movers_direction_filter():
    up = top_movers(sample_obs(), direction="up")
    assert all(m["delta_jpy"] > 0 for m in up["movers"])
    names = {m["name"] for m in up["movers"]}
    assert "リザードン SR" in names and "ピカチュウ レア" not in names

    down = top_movers(sample_obs(), direction="down")
    assert all(m["delta_jpy"] < 0 for m in down["movers"])
    assert any(m["name"] == "ピカチュウ レア" for m in down["movers"])
