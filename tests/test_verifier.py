"""
Tests for application/verifier.py — ActionVerifier.verify_retweet の判定ロジック

2026-08-26: 判別不能(unresolved)は success=False に変更（API偽装成功検出のため）。
  従来 success=True(verify_unresolved) で成功扱いし、RT未反映を検出できなかった。
  このテストは新仕様を固定し、regression（success=True への後退）を防ぐ。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unittest.mock import MagicMock

from kensho.application.verifier import ActionVerifier


def _make_page(*, unretweet: bool = False, retweet: bool = False) -> MagicMock:
    """query_selector が指定状態を返すモックページ"""
    page = MagicMock()

    def _qsel(selector: str):
        if selector == '[data-testid="unretweet"]' and unretweet:
            return MagicMock()
        if selector == '[data-testid="retweet"]' and retweet:
            return MagicMock()
        return None

    page.query_selector.side_effect = _qsel
    return page


class TestVerifyRetweet:
    def test_retweeted_is_success(self) -> None:
        """unretweetボタン存在 → リポスト済み → success=True"""
        page = _make_page(unretweet=True)
        result = ActionVerifier.verify_retweet(page, "123456")
        assert result.success is True
        assert result.detail == "retweeted"

    def test_not_retweeted_is_failure(self) -> None:
        """retweetボタン存在（未リポスト） → success=False"""
        page = _make_page(retweet=True)
        result = ActionVerifier.verify_retweet(page, "123456")
        assert result.success is False
        assert result.detail == "not_retweeted"

    def test_unresolved_is_failure(self) -> None:
        """ボタン状態が判別不能 → success=False（2026-08-26修正・偽装成功防止）"""
        page = _make_page()  # どちらのボタンも無し
        result = ActionVerifier.verify_retweet(page, "123456")
        assert result.success is False
        assert result.detail.startswith("verify_unresolved:")

    def test_no_url_is_failure(self) -> None:
        """tweet_idもfallback_urlも無し → unresolved(no_url) = 失敗"""
        page = _make_page()
        result = ActionVerifier.verify_retweet(page, "", fallback_url="")
        assert result.success is False
        assert result.detail == "verify_unresolved:no_url"

    def test_goto_error_is_failure(self) -> None:
        """ページ遷移エラー → unresolved(goto_error) = 失敗"""
        page = _make_page()
        page.goto.side_effect = Exception("timeout")
        result = ActionVerifier.verify_retweet(page, "123456")
        assert result.success is False
        assert result.detail.startswith("verify_unresolved:goto_error:")
