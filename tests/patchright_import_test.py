"""Tests for patchright — stealth Playwright の pin 検証とエンジン選択ルーティング。

- patchright が requirements.txt で 1.62.3 に pin されていること
- 導入時 _PATCHRIGHT_AVAILABLE が True になること
- Firefox 起動（create_browser）は patchright の firefox driver が不安定なため
  常に標準 playwright へルーティングされ、既存接続が温存されること
  （patchright は chromium-stealth 経路にのみ将来利用）
"""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import kensho.application.browser as browser_mod
from kensho.application.browser import close_browser, create_browser

PINNED_VERSION = "1.62.3"


# ═══════════════════════════════════════════════════════════════
# TestPin — patchright の導入状態・pin 検証
# ═══════════════════════════════════════════════════════════════


class TestPin:
    def test_patchright_installed_and_pinned(self) -> None:
        """patchright が導入済みで requirements.txt の pin 値と一致すること"""
        m = pytest.importorskip("patchright")
        ver = importlib.metadata.version("patchright")
        assert ver == PINNED_VERSION, f"patchright version {ver} != {PINNED_VERSION}"
        # importorskip が実モジュールを解決できること
        assert m is not None

    def test_available_flag_true_when_installed(self) -> None:
        """導入済み環境では _PATCHRIGHT_AVAILABLE が True"""
        pytest.importorskip("patchright")
        assert browser_mod._PATCHRIGHT_AVAILABLE is True

    def test_std_playwright_handle_present(self) -> None:
        """Firefox 用の標準 playwright ハンドルが必ず存在する（フォールバック温存）"""
        assert browser_mod._std_sync_playwright is not None

    def test_requirement_pinned_in_requirements_txt(self) -> None:
        """requirements.txt に patchright==1.62.3 が pin されている"""
        req = Path(__file__).parent.parent / "requirements.txt"
        lines = req.read_text(encoding="utf-8").splitlines()
        assert any("patchright==1.62.3" in line for line in lines)


# ═══════════════════════════════════════════════════════════════
# TestEngineRouting — Firefox 起動は常に標準 playwright（patchright 非使用）
# ═══════════════════════════════════════════════════════════════


class TestEngineRouting:
    def _mock_chain(self) -> MagicMock:
        """標準 playwright factory → pw → browser → ctx → page のモック連鎖を作る"""
        page = MagicMock()
        page.viewport_size = {"width": 1366, "height": 768}
        ctx = MagicMock()
        ctx.pages = []  # 既存ページなし → new_page() が呼ばれる
        ctx.new_page.return_value = page
        browser = MagicMock()
        browser.pages = []  # Browser 直下扱い → contexts 無し分岐は踏まないよう pages を空に
        browser.contexts = []
        browser.new_context.return_value = ctx
        pw = MagicMock()
        pw.firefox.launch.return_value = browser
        factory = MagicMock()
        factory.return_value.start.return_value = pw
        return factory

    def test_firefox_launch_uses_std_playwright(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """create_browser が patchright ではなく標準 playwright で Firefox を起動する"""
        if browser_mod._std_sync_playwright is None:
            pytest.skip("標準 playwright が未導入")
        factory = self._mock_chain()
        monkeypatch.setattr(browser_mod, "_std_sync_playwright", factory)

        # patchright ハンドルが呼ばれたら即失敗させる（使われてはならない）
        def _forbidden() -> None:
            raise AssertionError("create_browser が patchright factory を呼び出してはならない")

        monkeypatch.setattr(browser_mod, "_patchright_sync_playwright", _forbidden)

        _, launch_browser, _ctx, _page = create_browser(account_key=None, session_file=None, headless=True)

        factory.return_value.start.assert_called_once()
        factory.return_value.start.return_value.firefox.launch.assert_called_once()
        assert launch_browser is factory.return_value.start.return_value.firefox.launch.return_value

    def test_close_browser_works_with_mock(self) -> None:
        """close_browser がモックでも例外なく動く（既存挙動の回帰）"""
        browser = MagicMock()
        ipw = MagicMock()
        close_browser(ipw, browser, log=None)
        browser.close.assert_called_once()
        ipw.stop.assert_called_once()
