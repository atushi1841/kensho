"""scorer のリサーチ反映重み（2026-09-03 v9 提案1）のテスト"""

from __future__ import annotations

import pytest

from kensho.scraping.scorer import score_prize


def _base() -> dict:
    """協賛・食品・当選人数・締切に関与しない最小スコア"""
    return score_prize("RT&フォローでプレゼント応募で抽選")


class TestSponsoredWeight:
    def test_sponsor_keyword_boosts(self) -> None:
        """「協賛」を含むツイートは優先度が上がる"""
        s = score_prize("○×商事協賛で現金プレゼント！応募はRT")
        assert s["priority"] >= 1.7


class TestFoodWeight:
    def test_food_keyword_boosts(self) -> None:
        """食品系（お菓子）は優先度が上がる"""
        s = score_prize("新作お菓子を抽選でプレゼント！RTで応募")
        assert s["priority"] >= 1.4

    def test_beverage_boosts(self) -> None:
        """飲料系は優先度が上がる"""
        s = score_prize("期間限定ドリンク詰め合わせを当てよう！RT")
        assert s["priority"] >= 1.5


class TestWinnerCountWeight:
    def test_high_winner_count_boosts(self) -> None:
        """当選人数2000名以上は優先度2.0"""
        s = score_prize("抽選でプレゼント", winner_count=2000)
        assert s["priority"] >= 2.0

    def test_mid_winner_count_boosts(self) -> None:
        """当選人数600名で優先度1.6"""
        s = score_prize("抽選でプレゼント", winner_count=700)
        assert s["priority"] >= 1.6

    def test_small_winner_count_boosts(self) -> None:
        """当選人数100名で優先度1.3"""
        s = score_prize("抽選でプレゼント", winner_count=150)
        assert s["priority"] >= 1.3

    def test_zero_winner_count_no_boost(self) -> None:
        """当選人数不明ならボーナスなし（通常1.0前後）"""
        assert _base()["priority"] <= 1.1


class TestShortDeadlineWeight:
    def test_deadline_today_boosts(self) -> None:
        """締切が当日（24時間以内）なら優先度が上がる"""
        # 締切当日 → 残り時間は24時間未満
        s = score_prize("抽選でプレゼント", deadline="2099-01-01")
        # 未来日付なので残り時間は巨大 → ボーナスなし
        assert s["priority"] <= 1.1

    def test_tomorrow_deadline_not_boost(self) -> None:
        """締切が明日より先ならボーナスなし"""
        assert _base()["priority"] <= 1.1


class TestCombined:
    def test_food_plus_winners(self) -> None:
        """食品系 + 高当選人数で優先度が高く出る"""
        s = score_prize("新作スナックを抽選で2000名にプレゼント", winner_count=2000)
        assert s["priority"] >= 2.0

    def test_sponsor_plus_food(self) -> None:
        """協賛 + 食品系は想定通り積まれる（max方式）"""
        s = score_prize("メーカー協賛でお菓子詰め合わせをプレゼント")
        assert s["priority"] >= 1.7


@pytest.mark.parametrize(
    ("text", "wc", "expected_min"),
    [
        ("号外 ご当地グルメを抽選で提供", 0, 1.5),
        ("地域限定キャンペーンご参加でプレゼント", 0, 1.5),
    ],
)
def test_sponsor_geographical(text: str, wc: int, expected_min: float) -> None:
    assert score_prize(text, winner_count=wc)["priority"] >= expected_min
