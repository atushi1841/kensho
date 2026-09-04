"""scripts/overseas_saas_prospect_monitor.py のマッチ/下書き生成ロジックのテスト.

要点:
  - 高精度マッチ: ニッチ固有キーワードを持つ需要投稿を拾える
  - 偽陽性防止: 一般語(price/dataset/scrape/japan 等)だけで無関係投稿にマッチしない
  - 下書き生成: 1マッチ→1下書き、投稿固有の著者/タイトルが入る
  - 再利用テンプレ: catalog 全商品分が常に生成される
  - 日次窓: 直近 RECENT_DAYS 以内のみ採用

ネットワークなし(mock/アルゴリズムのみ)。実行: python -m pytest tests/test_overseas_prospect_monitor.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/scripts")
from overseas_saas_prospect_monitor import (  # noqa: E402
    DEMAND_PATTERNS,
    _build_products,
    build_draft,
    is_recent,
    match_products,
    proposal_template,
)


def _item(
    title: str,
    text: str = "",
    author: str = "hacker",
    created: str | None = None,
) -> dict:
    return {
        "title": title,
        "text": text,
        "author": author,
        "url": "https://news.ycombinator.com/item?id=12345678",
        "created_at": created or (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    }


# ── 高精度マッチ ──
def test_match_products_catches_niche_demand():
    it = _item(
        "Looking for a way to track used camera resale prices in Japan",
        text="Need to monitor Kitamura and Map Camera used DSLR prices over time.",
    )
    prods = match_products(it)
    names = [p.name for p in prods]
    assert "Japan Used Camera Market Scraper" in names, names


def test_match_products_mercari():
    it = _item("Looking for a Mercari Japan price scraper API")
    prods = match_products(it)
    assert "Mercari Japan Search Scraper" in [p.name for p in prods]


def test_match_products_anime_figure_dataset():
    it = _item(
        "Where to buy Japanese anime figure market price data?",
        text="Looking for anime figure resale price history as a CSV for research.",
    )
    names = [p.name for p in match_products(it)]
    assert "Japanese Anime Figure & Collectibles Market Price Dataset (Weekly CSV)" in names


# ── 偽陽性防止 ──
@pytest.mark.parametrize(
    "title,text",
    [
        ("Ask HN: Anyone using AI agents with SCPI equipment?", "Looking for others' experiences."),
        ("Launch HN: Nori Robotics – low-cost humanoid robot", "Collect large datasets for robotics."),
        ("Ask HN: Advice on Migrating from 1Password?", "Looking to move to a different password manager."),
        ("Resources to Get Good at Soldering?", "Any recommendations for a hobby bench setup."),
    ],
)
def test_match_products_no_false_positive(title: str, text: str):
    # 一般語(price/dataset/scrape/japan/hobby)が含まれていても、
    # 商品固有キーワードが無ければマッチしない=スパムにならない
    prods = match_products(_item(title, text))
    assert prods == [], f"偽陽性: {prods} for {title!r}"


# ── 需要シグナル ──
def test_demand_patterns_are_meaningful():
    assert "looking for" in DEMAND_PATTERNS
    assert any(p in DEMAND_PATTERNS for p in ["looking for", "need a tool"])


# ── 日次窓 ──
def test_recent_window_excludes_old_posts():
    old = _item("Looking for a tool", created=(datetime.now(UTC) - timedelta(days=60)).isoformat())
    assert not is_recent(old)


# ── 下書き生成 ──
def test_build_draft_includes_author_and_title():
    it = _item("Looking for a Mercari Japan price scraper", author="jp-researcher")
    prods = match_products(it)
    draft = build_draft(it, prods)
    assert draft is not None
    assert "jp-researcher" in draft
    assert "Mercari Japan price scraper" in draft
    # 商品URLが下書きに含まれる (post URL ではなく offering URL)
    assert "apify.com/apitor/mercari-japan-search-scraper" in draft


def test_build_draft_none_without_match():
    assert build_draft(_item("Ask HN: Which Docker UIs?", author="dockerfan"), []) is None


# ── 再利用テンプレ ──
def test_proposal_template_for_every_product():
    for p in _build_products():
        t = proposal_template(p)
        assert p.url in t
        assert p.price in t
        assert len(t) > 40


def test_catalog_has_expected_products():
    names = [p.name for p in _build_products()]
    assert "Japanese Anime Figure & Collectibles Market Price Dataset (Weekly CSV)" in names
    assert "Mercari Japan Search Scraper" in names
    assert len(names) >= 8
