"""backfill_deadlines.py — ローカル deadline 抽出と年齢凍結のテスト"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from backfill_deadlines import (
    backfill_local,
    extract_tweet_deadline,
    snowflake_to_dt,
)


def _mdi(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


class TestExtractTweetDeadline:
    def test_full_date_after_keyword(self) -> None:
        assert extract_tweet_deadline("応募締切：2026年9月30日", _mdi("2026-09-08")) == "2026-09-30"

    def test_keyword_md_slash(self) -> None:
        assert extract_tweet_deadline("✅締切:8/30(日)", _mdi("2026-09-08")) == "2026-08-30"

    def test_keyword_md_kanji(self) -> None:
        assert extract_tweet_deadline("応募期限 9月20日まで", _mdi("2026-09-08")) == "2026-09-20"

    def test_until_full_date(self) -> None:
        assert extract_tweet_deadline("本投稿を2026年9月6日 23:59までにRP", _mdi("2026-09-08")) == "2026-09-06"

    def test_until_md_with_weekday(self) -> None:
        # 「8月30日(日)午後11時59分まで」— 曜日を挟む
        assert extract_tweet_deadline("リポスト(8月30日(日)午後11時59分まで)", _mdi("2026-09-08")) == "2026-08-30"

    def test_period_range_uses_end_date(self) -> None:
        s1 = "🔗募集期間：8/25(火) ~ 8/27(木)"
        s2 = "2026年8月15日（土）～ 2026年8月30日（日）23:59"
        assert extract_tweet_deadline(s1, _mdi("2026-09-08")) == "2026-08-27"
        assert extract_tweet_deadline(s2, _mdi("2026-09-08")) == "2026-08-30"

    def test_empty_and_garbage(self) -> None:
        assert extract_tweet_deadline("") == ""
        assert extract_tweet_deadline("あいうえお") == ""

    def test_year_rollover_deep_past_month(self) -> None:
        # 10月末の「締切3月1日」は同年3月は238日超過去 → 翌年とみなす
        assert extract_tweet_deadline("締切3月1日", _mdi("2026-10-25")) == "2027-03-01"

    def test_year_no_rollover_future(self) -> None:
        assert extract_tweet_deadline("締切9月30日", _mdi("2026-09-08")) == "2026-09-30"


class TestSnowflake:
    def test_known_id(self) -> None:
        # 過去の実績ID: 950071636710535168
        dt = snowflake_to_dt(950071636710535168)
        assert dt is not None and dt.year >= 2016

    def test_invalid(self) -> None:
        assert snowflake_to_dt("") is None


class TestBackfillLocal:
    def _mk(self, **kw: Any) -> dict[str, Any]:
        base: dict[str, Any] = {"source": "cpmeikan", "deadline": "", "tweet_text": "", "x_url": ""}
        base.update(kw)
        return base

    def test_extract_from_text(self) -> None:
        items = [self._mk(tweet_text="締切:8/30(日)", x_url="https://x.com/a/status/2088189328665252134")]
        x, y, still = backfill_local(items)
        assert x == 1 and items[0]["deadline"] == "2026-08-30"

    def test_freezes_old_tweet(self) -> None:
        # 古い投稿で抽出不能 → 投稿日を deadline 実値へ + expired
        old_id = str(int(1e18))  # 2017年前後の snowflake → 明らかに21日超
        items = [self._mk(tweet_text="キャンペーン開催中", x_url=f"https://x.com/a/status/{old_id}", tweet_id=old_id)]
        e, f, s = backfill_local(items)
        assert f == 1 and e == 0 and s == 0
        assert items[0]["expired"] is True
        assert items[0]["deadline_source"] == "age_freeze"
        # deadline は投稿日 = 過去
        assert items[0]["deadline"] < datetime.now().strftime("%Y-%m-%d")

    def test_young_unparseable_left_as_is(self) -> None:
        # 現在〜3日前の snowflake → 21日未満 → deadline は空のまま（適用候補として残す）
        now_ms = int(datetime.now().timestamp() * 1000)
        epoch_ms = 1288834974657
        tid = ((now_ms - epoch_ms - 3 * 86400 * 1000) << 22) | 1
        items = [self._mk(tweet_text="応募方法: フォロー＆RT", tweet_id=str(tid))]
        e, f, s = backfill_local(items)
        assert e == 0 and f == 0 and s == 1
        assert items[0]["deadline"] == ""

    def test_respects_existing_deadline(self) -> None:
        items = [self._mk(deadline="2026-09-20", tweet_text="締切:8/30(日)")]
        e, f, s = backfill_local(items)
        assert e == 0 and items[0]["deadline"] == "2026-09-20"
