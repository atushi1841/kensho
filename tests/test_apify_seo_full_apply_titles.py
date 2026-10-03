"""scripts/apify_seo_full_apply.py の生成タイトル重複の回帰テスト。

2026-10-03 の実測で、汎用ラベルへのフォールバック（"Japan market data"）と
固定接頭辞 "Japan " の連結により "Japan Japan market data Scraper — Price,
Listings, JSON" が19本のアクターに同一で付与されていた。これを恒久修正した
ことの回帰テスト。

ネットワーク不使用（純関数のみ）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apify_seo_full_apply as mod

# 実測で重複タイトルが付いていたアクター名（フォールバック経路を通るもの）
FALLBACK_NAMES = [
    "goobike-motorcycle-scraper",
    "suumo-japan-real-estate-scraper",
    "suumo-japan-real-estate-scraper-cn",
    "suumo-japan-real-estate-scraper-kr",
    "kimono-market-scraper",
    "kimono-market-scraper-cn",
    "rakuten-market-scraper",
    "upgarage-parts-scraper",
    "japan-figure-plamo-resale-price-stats",
]


def _has_adjacent_duplicate(text: str) -> bool:
    words = [w.strip(",.;:—–-").lower() for w in text.split()]
    words = [w for w in words if w]
    return any(words[i] == words[i + 1] for i in range(len(words) - 1))


def test_dedupe_adjacent_collapses_repeats() -> None:
    assert mod._dedupe_adjacent("Japan Japan market data Scraper") == "Japan market data Scraper"
    assert mod._dedupe_adjacent("Scrapes Japan market data data from") == "Scrapes Japan market data from"
    assert mod._dedupe_adjacent("no repeats here") == "no repeats here"


def test_fallback_label_is_never_generic_japan() -> None:
    """フォールバックでも "Japan" 始まりのラベルを返さない（二重接頭辞の防止）。"""
    for name in FALLBACK_NAMES:
        label, _ = mod.infer_usage(name)
        assert not label.lower().startswith("japan"), f"{name} -> {label}"
        assert label.strip() != "market data" or name == "", f"{name} が汎用ラベルに落ちている"


def test_generated_titles_have_no_adjacent_duplicates() -> None:
    for name in FALLBACK_NAMES:
        label, usage = mod.infer_usage(name)
        for text in (
            mod.build_seo_title(name, label),
            mod.build_title(name, label),
            mod.build_seo_description(name, label, usage),
            mod.build_description(name, label, usage),
        ):
            assert not _has_adjacent_duplicate(text), f"{name}: {text}"


def test_generated_titles_are_unique_per_actor() -> None:
    titles = {}
    for name in FALLBACK_NAMES:
        label, _ = mod.infer_usage(name)
        titles[name] = mod.build_seo_title(name, label)
    assert len(set(titles.values())) == len(titles), titles


def test_generated_fields_respect_char_limits() -> None:
    for name in FALLBACK_NAMES:
        label, usage = mod.infer_usage(name)
        assert len(mod.build_seo_title(name, label)) <= mod.CHAR_LIMITS["seoTitle"]
        assert len(mod.build_title(name, label)) <= mod.CHAR_LIMITS["title"]
        assert (
            len(mod.build_seo_description(name, label, usage))
            <= mod.CHAR_LIMITS["seoDescription"]
        )
        assert len(mod.build_description(name, label, usage)) <= mod.CHAR_LIMITS["description"]
