"""tests/test_reddit_comment_writer.py — コメント草稿の品質ゲート（ネットワーク不使用）

2026-10-03 の改修で、定型文の寄せ集め＋埋め草による水増しを廃止し、
LLMが書いたスレ固有コメントに品質ゲートをかける方式へ変えた。
そのゲートの回帰テスト。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import reddit_comment_writer as w

GOOD = (
    "I've been logging second-hand listings across a few Japanese shops, and the gap "
    "between asking prices and what actually sells is bigger than most people assume."
)


def test_good_comment_passes() -> None:
    ok, reason = w.quality_check(GOOD)
    assert ok, reason


def test_old_template_filler_is_rejected() -> None:
    """旧実装が生成していた定型文入りは不合格になる。"""
    old = (
        "これ、実はよくある話ですね。 周りでも似たような話を何度か聞きました。 "
        "参考になれば幸いです。 参考になれば幸いです。 ぜひ皆さんの意見も聞かせてください。 "
        "何か別の視点があれば教えて下さい。 私も同じような経験があるので、お力になれれば。"
    )
    assert len(old) > w.MIN_CHARS  # 長さで弾かれていないことを保証する
    ok, reason = w.quality_check(old)
    assert not ok
    assert reason.startswith("banned_phrase") or reason.startswith("not_english")


def test_repeated_sentence_rejected() -> None:
    text = (
        "The asking price is not the selling price in this market. "
        "The asking price is not the selling price in this market."
    )
    ok, reason = w.quality_check(text)
    assert not ok
    assert reason == "repeated_sentence"


def test_link_rejected() -> None:
    text = GOOD + " Full table here: https://example.com/data"
    ok, reason = w.quality_check(text)
    assert not ok
    assert reason == "contains_link"


def test_non_english_rejected() -> None:
    text = "これは日本語のコメントです。" * 10
    assert len(text) > w.MIN_CHARS
    ok, reason = w.quality_check(text)
    assert not ok
    assert reason.startswith("not_english")


def test_length_bounds() -> None:
    assert w.quality_check("短い").__getitem__(1).startswith("too_short")
    long_text = GOOD + " " + ("This adds more context and detail to the comment. " * 10)
    assert w.quality_check(long_text).__getitem__(1).startswith("too_long")


def test_meta_reasoning_rejected() -> None:
    """思考過程の垂れ流しは不合格（ルーターの推論モデル対策）。"""
    text = (
        "We need to produce a comment in English. Rules: 2-4 sentences, between 120 "
        "and 350 characters, and we must not mention our own products at all here."
    )
    assert len(text) > w.MIN_CHARS
    ok, reason = w.quality_check(text)
    assert not ok
    assert reason.startswith("meta_marker")


def test_extract_comment_with_and_without_closing_tag() -> None:
    assert w._extract_comment("noise <comment>hello there</comment> more") == "hello there"
    # stop シーケンスで閉じタグが落ちた場合も本文を取れること
    assert w._extract_comment("<comment>hello there") == "hello there"
    assert w._extract_comment("no tags at all") == ""


def test_numbers_guard_blocks_fabrication() -> None:
    """実データに無い数値は弾く（292件→2,920件と水増しした実例の回帰）。"""
    title = "Price variation across outlets of the same brand"
    fact = {"median": 8300, "p25": 4200, "p75": 16000, "count": 292}
    allowed = w.allowed_numbers_for(title, fact)
    fabricated = (
        "I logged 2,920 listings from the same shops and the median came out at "
        "8,300 yen, which is a 29200 percent spread across the whole category."
    )
    assert len(fabricated) > w.MIN_CHARS
    ok, reason = w.quality_check(fabricated, allowed_numbers=allowed)
    assert not ok
    assert reason.startswith("unsupported_number")


def test_numbers_guard_allows_real_values_and_title_numbers() -> None:
    title = "I contacted 50 dental practices"
    fact = {"median": 8300, "p25": 4200, "p75": 16000, "count": 292}
    allowed = w.allowed_numbers_for(title, fact)
    text = (
        "Only 50 answered at all, and in my own 292 rows the median asking price sat "
        "at 8,300 JPY, so the spread is wider than people expect in this kind of market."
    )
    assert len(text) > w.MIN_CHARS
    ok, reason = w.quality_check(text, allowed_numbers=allowed)
    assert ok, reason


def test_english_ratio() -> None:
    assert w.english_ratio("plain english text") == 1.0
    assert w.english_ratio("日本語だけ") < 0.5
