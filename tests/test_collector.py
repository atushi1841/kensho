"""
Tests for scraping/collector.py — extract_deadline_and_winners v3.3,
is_x_url, _is_expired
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.collector import (
    _dedup_x_url_merge,
    _is_expired,
    _normalize_x_url,
    extract_deadline_and_winners,
    is_x_url,
)


class TestIsExpired:
    """_is_expired: 締切日から30日経過判定"""

    def test_empty_deadline(self) -> None:
        assert _is_expired("") is False

    def test_future_deadline(self) -> None:
        future = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        assert _is_expired(future) is False

    def test_past_deadline_excluded(self) -> None:
        # 締切日を過ぎた案件は即時除外（_EXPIRY_DAYS=0 新仕様）
        past = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d")
        assert _is_expired(past) is True

    def test_deadline_today_not_expired(self) -> None:
        # 締切日当日は応募可能 → 除外しない
        today = datetime.now().strftime("%Y-%m-%d")
        assert _is_expired(today) is False

    def test_past_over_30_days(self) -> None:
        past = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d")
        assert _is_expired(past) is True

    def test_with_custom_now(self) -> None:
        now = datetime(2026, 6, 1)
        # 締切日を過ぎたもの(翌日以降)は除外
        assert _is_expired("2026-05-01", now) is True
        assert _is_expired("2026-05-15", now) is True
        # 締切日当日は応募可能
        assert _is_expired("2026-06-01", now) is False
        # 未来は応募可能
        assert _is_expired("2026-07-01", now) is False


class TestIsXUrl:
    """is_x_url: ツイートURLか判定（アカウントページは除外）"""

    def test_x_com_status(self) -> None:
        assert is_x_url("https://x.com/username/status/123") is True

    def test_twitter_com_status(self) -> None:
        assert is_x_url("https://twitter.com/username/status/123") is True

    def test_x_com_status_with_hash(self) -> None:
        """#fragment 付き — is_x_url は URL をそのまま判定する"""
        assert is_x_url("https://x.com/username/status/123#abc") is True

    def test_account_page_x_com(self) -> None:
        """アカウントページは False"""
        assert is_x_url("https://x.com/username") is False

    def test_account_page_with_hash(self) -> None:
        """アカウントページ + tracking hash"""
        assert is_x_url("https://x.com/username#508") is False

    def test_other(self) -> None:
        assert is_x_url("https://example.com") is False
        assert is_x_url("https://knshow.com/detail/abc") is False
        assert is_x_url("") is False


class TestExtractDeadline:
    """extract_deadline_and_winners: v3.3 title優先 + サイドバー除外"""

    # ── 正常系: titleタグから抽出 ──

    def test_deadline_from_title(self) -> None:
        """titleタグ: 【〆切07月01日】"""
        html = "<title>【毎日当たる】商品名を10000名様にプレゼント【〆切07月01日】提供者名</title>"
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-07-01"
        assert winners == 10000

    def test_deadline_bracket_title(self) -> None:
        """titleタグ: [〆切07月15日]"""
        html = "<title>[〆切07月15日] キャンペーン名</title>"
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-07-15"

    # ── 正常系: 応募締切日spanタグ ──

    def test_deadline_from_expiredatetime(self) -> None:
        """応募締切日の data-expiredatetime 属性"""
        html = (
            '<p>応募締切日：<strong><span class="expiredatetime-display" '
            "data-expiredatetime='2026-07-01'>2026-07-01</span></strong></p>"
        )
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-07-01"

    # ── 正常系: 締切:テキスト ──

    def test_deadline_from_text(self) -> None:
        """締切:6月30日"""
        html = "<title>ダミー</title>  <p> 締切:6月30日 </p>"
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-06-30"

    def test_deadline_with_time(self) -> None:
        """締切:6月24日 20:00"""
        html = "<title>ダミー</title>  <p> 締切:6月24日 20:00 </p>"
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-06-24"

    # ── 当選人数抽出 ──

    def test_winners_from_tousenST(self) -> None:
        """<strong class=\"tousenST\"> 10,000</strong>名様"""
        html = '<strong class="tousenST"> 10,000</strong>名様'
        deadline, winners = extract_deadline_and_winners(html)
        assert winners == 10000

    def test_winners_from_title(self) -> None:
        """titleから: 10000名様にプレゼント"""
        html = "<title>10000名様にプレゼント【〆切07月01日】</title>"
        deadline, winners = extract_deadline_and_winners(html)
        assert winners == 10000

    def test_winners_commas_in_title(self) -> None:
        """titleからカンマ付き: 10,000,000名様"""
        html = "<title>10,000,000名様に当たる【〆切06月27日】</title>"
        deadline, winners = extract_deadline_and_winners(html)
        assert winners == 10000000

    # ── 欠損ケース ──

    def test_no_deadline(self) -> None:
        html = "素敵なプレゼントキャンペーン"
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == ""
        assert winners == 0

    def test_no_winners(self) -> None:
        """当選人数不明"""
        html = "<title>ダミータイトル【〆切08月01日】</title>当選人数不明"
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-08-01"

    # ── サイドバー無視確認 ──

    def test_ignores_sidebar(self) -> None:
        """サイドバーの「応募締切日：年/月/日」を無視してtitleを優先"""
        html = (
            "<title>【毎日当たる】限定品を500名様にプレゼント【〆切07月15日】</title>"
            '<div class="sidebar">'
            "<li>商品A <p>当選人数：170,000名様　締切：6月29日</p></li>"
            "<li>商品B <p>当選人数：50,000名様　締切：6月30日</p></li>"
            "</div>"
        )
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-07-15"
        assert winners == 500


class TestKnpwDeadlineExtraction:
    """knshow.com の実HTMLに対する deadline/winners 抽出テスト"""

    # 実際のknshow詳細ページから取得したHTML断片
    KNSHOW_HTML_TITLE = (
        "<title>【毎日・その場で当たる】"
        "クーリッシュバニラ1個 無料引換券を10000名様にプレゼント"
        "【〆切07月01日】ロッテ クーリッシュ</title>"
    )

    KNSHOW_HTML_TOUSEN = '<strong class="tousenST"> 10,000</strong>名様'

    KNSHOW_HTML_EXPIRY = (
        "<p>応募締切日：<strong>"
        '<span class="expiredatetime-display" '
        "data-expiredatetime='2026-07-01'>2026-07-01</span>"
        "</strong></p>"
    )

    def test_title_deadline_extraction(self) -> None:
        """実HTMLのtitleタグから締切を正しく抽出"""
        deadline, winners = extract_deadline_and_winners(self.KNSHOW_HTML_TITLE)
        assert deadline == "2026-07-01"
        assert winners == 10000

    def test_tousen_st_extraction(self) -> None:
        """tousenSTクラスから当選人数を抽出"""
        html: str = self.KNSHOW_HTML_TOUSEN
        deadline, winners = extract_deadline_and_winners(html)
        assert winners == 10000

    def test_expiredatetime_extraction(self) -> None:
        """expiredatetime-display属性から締切を抽出"""
        html: str = self.KNSHOW_HTML_EXPIRY
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-07-01"

    def test_full_page_pattern(self) -> None:
        """実際のknshowページ構成を模したHTML"""
        html: str = (
            self.KNSHOW_HTML_TITLE
            + '<meta name="description" content="懸賞情報 (07月01日マデ)"/>'
            + self.KNSHOW_HTML_EXPIRY
            + self.KNSHOW_HTML_TOUSEN
            + '<div class="sidebar">'
            + "<p>当選人数：170,000名様　締切：6月29日</p>"
            + "<p>当選人数：50,000名様　締切：6月30日</p>"
            + "</div>"
        )
        deadline, winners = extract_deadline_and_winners(html)
        assert deadline == "2026-07-01", f"Expected 2026-07-01, got {deadline}"
        assert winners == 10000, f"Expected 10000, got {winners}"


class TestNormalizeXUrl:
    """_normalize_x_url: URL表記揺れの正規化（2026-08-25追加）"""

    def test_i_web_status_normalized(self) -> None:
        """/i/web/status/ 形式もツイートIDキーに正規化"""
        assert _normalize_x_url("https://x.com/i/web/status/1234567890") == "x.com/status/1234567890"

    def test_twitter_com_normalized(self) -> None:
        """twitter.com もツイートIDキーに正規化"""
        assert _normalize_x_url("https://twitter.com/foo/status/123") == "x.com/status/123"

    def test_query_and_fragment_stripped(self) -> None:
        """末尾の ?クエリ / #フラグメント を除去"""
        assert _normalize_x_url("https://x.com/foo/status/123?s=20#x") == "x.com/status/123"

    def test_username_variant_same_key(self) -> None:
        """ユーザー名表記の有無にかかわらず同一ツイートは同一キー"""
        assert _normalize_x_url("https://x.com/foo/status/123") == _normalize_x_url("https://x.com/i/web/status/123")


class TestDedupXUrlMerge:
    """_dedup_x_url_merge: URL表記揺れ重複の統合（2026-08-25追加）"""

    def test_variant_entries_collapsed(self) -> None:
        """/status/ と /i/web/status/ の同一ツイートが1エントリに統合される"""
        a: dict[str, Any] = {
            "x_url": "https://x.com/foo/status/123",
            "applied": {"atushi16": "2026-08-24T00:00:00"},
            "tweet_text": "short",
            "deadline": "",
        }
        b: dict[str, Any] = {
            "x_url": "https://x.com/i/web/status/123",
            "applied": {"kudou": "2026-08-24T01:00:00"},
            "tweet_text": "longer text here",
            "deadline": "2026-09-01",
        }
        merged = _dedup_x_url_merge([a, b])
        assert len(merged) == 1
        m = merged[0]
        assert m["applied"]["atushi16"] == "2026-08-24T00:00:00"
        assert m["applied"]["kudou"] == "2026-08-24T01:00:00"
        assert m["tweet_text"] == "longer text here"
        assert m["deadline"] == "2026-09-01"
        assert "/i/web/status/" not in m["x_url"]

    def test_distinct_tweets_kept(self) -> None:
        """別ツイートは統合されない"""
        a = {"x_url": "https://x.com/foo/status/111", "applied": {}}
        b = {"x_url": "https://x.com/bar/status/222", "applied": {}}
        assert len(_dedup_x_url_merge([a, b])) == 2

    def test_identical_entries_merged(self) -> None:
        """完全一致のx_urlも従来通り統合"""
        a = {"x_url": "https://x.com/foo/status/123", "applied": {"atushi16": "2026-08-24T00:00:00"}}
        b = {"x_url": "https://x.com/foo/status/123", "applied": {"kudou": "2026-08-24T01:00:00"}}
        merged = _dedup_x_url_merge([a, b])
        assert len(merged) == 1
        assert set(merged[0]["applied"].keys()) == {"atushi16", "kudou"}

    def test_tweet_id_backfilled(self) -> None:
        """tweet_id未保存の既存アイテムにx_urlからバックフィルされる（2026-08-26追加）"""
        a: dict[str, Any] = {
            "x_url": "https://x.com/foo/status/987654321",
            "applied": {},
        }
        merged = _dedup_x_url_merge([a])
        assert merged[0]["tweet_id"] == "987654321"

    def test_tweet_id_backfilled_iweb(self) -> None:
        """/i/web/status/ 形式のx_urlからもtweet_idが抽出される（監査n/a解消）"""
        a: dict[str, Any] = {
            "x_url": "https://x.com/i/web/status/555444333",
            "applied": {},
        }
        merged = _dedup_x_url_merge([a])
        assert merged[0]["tweet_id"] == "555444333"

    def test_tweet_id_preserved_if_present(self) -> None:
        """既存のtweet_idフィールドは上書きされない"""
        a: dict[str, Any] = {
            "x_url": "https://x.com/foo/status/123",
            "tweet_id": "custom_id",
            "applied": {},
        }
        merged = _dedup_x_url_merge([a])
        assert merged[0]["tweet_id"] == "custom_id"
