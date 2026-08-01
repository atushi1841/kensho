"""
Tests for scraping/collector.py — extract_deadline_and_winners v3.3,
is_x_url, _is_expired
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.collector import _is_expired, extract_deadline_and_winners, is_x_url


class TestIsExpired:
    """_is_expired: 締切日から30日経過判定"""

    def test_empty_deadline(self) -> None:
        assert _is_expired("") is False

    def test_future_deadline(self) -> None:
        future = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        assert _is_expired(future) is False

    def test_past_within_30_days(self) -> None:
        past = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d")
        assert _is_expired(past) is False

    def test_past_over_30_days(self) -> None:
        past = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d")
        assert _is_expired(past) is True

    def test_with_custom_now(self) -> None:
        now = datetime(2026, 6, 1)
        assert _is_expired("2026-05-01", now) is True
        assert _is_expired("2026-05-15", now) is False
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
