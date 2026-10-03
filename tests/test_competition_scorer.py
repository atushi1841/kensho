"""
Tests for competition score calculation (t_fb291adc).
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_items() -> list[dict[str, Any]]:
    """代表アイテム（全国型・地方型・高額・低額・期限切れ）。"""
    now = datetime.now()
    future = (now + timedelta(days=10)).strftime("%Y-%m-%d")
    past = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    return [
        {
            "tweet_text": "フォロー＆RTでAmazonギフト券1万円分が当たる！",
            "winner_count": 5,
            "deadline": future,
            "prize_score": {"estimated_value_jpy": 10000},
            "source": "knshow",
            "tweet_id": "1234567890123456789",
        },
        {
            "tweet_text": "東京のイベントで抽選で商品券が当たる！地方限定",
            "winner_count": 100,
            "deadline": future,
            "prize_score": {"estimated_value_jpy": 5000},
            "source": "kenshouclub",
            "tweet_id": "9876543210987654321",
        },
        {
            "tweet_text": "現金100万円プレゼント！ nationwide campaign",
            "winner_count": 3,
            "deadline": future,
            "prize_score": {"estimated_value_jpy": 1000000},
            "source": "knshow",
            "tweet_id": "1111111111111111111",
        },
        {
            "tweet_text": "もう終わりました...",
            "winner_count": 0,
            "deadline": past,
            "prize_score": {"estimated_value_jpy": 0},
            "source": "ken-kaku",
            "tweet_id": "2222222222222222222",
        },
    ]


from datetime import timedelta
from kensho.scraping.competition_scorer import (
    COMPETITION_SCORE_KEY,
    compute_competition_score,
    compute_batch_competition_scores,
    save_competition_scores,
)


# ── compute_competition_score ─────────────────────────────────────────────────

class TestComputeCompetitionScore:
    def test_returns_dict_with_required_keys(self, sample_items: list[dict[str, Any]]) -> None:
        result = compute_competition_score(sample_items[0])
        assert isinstance(result, dict)
        assert "score" in result
        assert "factors" in result
        assert "factors_raw" in result
        assert set(result["factors"].keys()) == {"engagement", "prize", "deadline", "event_type"}

    def test_score_in_range(self, sample_items: list[dict[str, Any]]) -> None:
        for item in sample_items:
            score = compute_competition_score(item)["score"]
            assert 0.0 <= score <= 100.0, f"score out of range: {score}"

    def test_high_prize_value_increases_score(self) -> None:
        item_low = {"tweet_text": "1000円商品", "winner_count": 5, "deadline": "2026-10-20", "prize_score": {"estimated_value_jpy": 1000}, "source": "knshow", "tweet_id": "1"}
        item_high = {"tweet_text": "100万円商品", "winner_count": 5, "deadline": "2026-10-20", "prize_score": {"estimated_value_jpy": 1000000}, "source": "knshow", "tweet_id": "2"}

        score_low = compute_competition_score(item_low)["factors"]["prize"]
        score_high = compute_competition_score(item_high)["factors"]["prize"]
        assert score_high > score_low

    def test_near_deadline_has_lower_score(self) -> None:
        from datetime import timedelta
        now = datetime.now()
        item_far = {"tweet_text": "商品", "winner_count": 10, "deadline": (now + timedelta(days=30)).strftime("%Y-%m-%d"), "prize_score": {"estimated_value_jpy": 5000}, "source": "knshow", "tweet_id": "1"}
        item_near = {"tweet_text": "商品", "winner_count": 10, "deadline": (now + timedelta(days=1)).strftime("%Y-%m-%d"), "prize_score": {"estimated_value_jpy": 5000}, "source": "knshow", "tweet_id": "2"}

        score_far = compute_competition_score(item_far)["factors"]["deadline"]
        score_near = compute_competition_score(item_near)["factors"]["deadline"]
        # 締切が近いほど競争率は低い（応募者が集まらない）
        assert score_near < score_far

    def test_expired_deadline_has_low_score(self, sample_items: list[dict[str, Any]]) -> None:
        # 期限切れアイテム（4番目）- 期限切れなので競争率は低く、優先度も低い
        expired = sample_items[3]
        score = compute_competition_score(expired)["score"]
        # 期限切れはスコアが低くなる（優先度が下がる）
        assert score < 50.0, f"Expected low score for expired deadline, got {score}"

    def test_local_event_has_lower_score(self) -> None:
        item_national = {"tweet_text": "全国キャンペーン", "winner_count": 10, "deadline": "2026-10-20", "prize_score": {"estimated_value_jpy": 5000}, "source": "knshow", "tweet_id": "1"}
        item_local = {"tweet_text": "東京地方イベント", "winner_count": 10, "deadline": "2026-10-20", "prize_score": {"estimated_value_jpy": 5000}, "source": "kenshouclub", "tweet_id": "2"}

        score_national = compute_competition_score(item_national)["factors"]["event_type"]
        score_local = compute_competition_score(item_local)["factors"]["event_type"]
        assert score_national > score_local


# ── normalize_winner_count ────────────────────────────────────────────────────

class TestNormalizeWinnerCount:
    def test_zero_returns_zero(self) -> None:
        from kensho.scraping.scorer import normalize_winner_count
        assert normalize_winner_count(0) == 0.0

    def test_missing_returns_zero(self) -> None:
        from kensho.scraping.scorer import normalize_winner_count
        assert normalize_winner_count(None) == 0.0
        assert normalize_winner_count("") == 0.0

    def test_monotonic(self) -> None:
        from kensho.scraping.scorer import normalize_winner_count
        scores = [normalize_winner_count(wc) for wc in [1, 10, 100, 1000]]
        assert all(scores[i] <= scores[i + 1] for i in range(len(scores) - 1))

    def test_cap_at_1000(self) -> None:
        from kensho.scraping.scorer import normalize_winner_count
        # 1000名で満点（1.0）
        assert normalize_winner_count(1000) >= 0.99
        assert normalize_winner_count(5000) >= 0.99


# ── compute_batch_competition_scores ─────────────────────────────────────────

class TestComputeBatchCompetitionScores:
    def test_returns_mapping(self, sample_items: list[dict[str, Any]]) -> None:
        result = compute_batch_competition_scores(sample_items)
        assert isinstance(result, dict)
        assert len(result) == len(sample_items)

    def test_keys_match_tweet_ids(self, sample_items: list[dict[str, Any]]) -> None:
        result = compute_batch_competition_scores(sample_items)
        expected_keys = {item.get("tweet_id", "") or item.get("x_url", "") for item in sample_items}
        assert set(result.keys()) == expected_keys


# ── save_competition_scores ──────────────────────────────────────────────────

class TestSaveCompetitionScores:
    def test_saves_and_loads(self, tmp_path: Path) -> None:
        scores = {
            "tweet1": {"score": 75.5, "factors": {"engagement": 80.0, "prize": 70.0, "deadline": 75.0, "event_type": 75.0}},
            "tweet2": {"score": 25.0, "factors": {"engagement": 20.0, "prize": 30.0, "deadline": 25.0, "event_type": 25.0}},
        }
        output_path = tmp_path / "competition_score.json"
        save_competition_scores(scores, output_path)

        assert output_path.exists()
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        assert loaded == scores

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        scores = {"tweet1": {"score": 50.0}}
        output_path = tmp_path / "nested" / "dir" / "competition_score.json"
        save_competition_scores(scores, output_path)
        assert output_path.exists()
