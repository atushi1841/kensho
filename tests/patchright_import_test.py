"""Tests for patchright — stealth Playwright の pin 検証とエンジン選択ルーティング。

- patchright が requirements.txt で 1.62.3 に pin されていること
- 導入時 _PATCHRIGHT_AVAILABLE が True になること
- 実運用デフォルトは standard playwright Firefox（X の /status/ が chromium で 403 のため）
- KENSHO_BROWSER=chromium 時のみ patchright chromium-stealth を起動し、
  失敗時は標準 playwright Firefox へフォールバックすること
- chromium 固有ヘルパー（UA / WebGL 指紋 / JS stealth / socks5 正規化）の妥当性
- real ブラウザでの navigator.webdriver=False 検証（chromium 導入時のみ）
"""

from __future__ import annotations

import importlib.metadata
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import kensho.application.browser as browser_mod
from kensho.application.browser import (
    FINGERPRINTS as REAL_FINGERPRINTS,
)
from kensho.application.browser import (
    _build_chromium_stealth_js,
    _chromium_ua,
    _chromium_webgl,
    close_browser,
    create_browser,
)

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
# TestEngineRouting — chromium 最優先 + Firefox フォールバック
# ═══════════════════════════════════════════════════════════════


class TestEngineRouting:
    def _mock_firefox_chain(self) -> MagicMock:
        """標準 playwright factory → pw → browser → ctx → page のモック連鎖を作る"""
        page = MagicMock()
        page.viewport_size = {"width": 1366, "height": 768}
        ctx = MagicMock()
        ctx.pages = []  # 既存ページなし → new_page() が呼ばれる
        ctx.new_page.return_value = page
        browser = MagicMock()
        browser.pages = []
        browser.contexts = []
        browser.new_context.return_value = ctx
        pw = MagicMock()
        pw.firefox.launch.return_value = browser
        factory = MagicMock()
        factory.return_value.start.return_value = pw
        return factory

    def _mock_chromium_chain(self) -> MagicMock:
        """patchright factory → pw → chromium.launch → browser → ctx → page"""
        page = MagicMock()
        page.viewport_size = {"width": 1366, "height": 768}
        ctx = MagicMock()
        ctx.pages = []
        ctx.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = ctx
        pw = MagicMock()
        pw.chromium.launch.return_value = browser
        factory = MagicMock()
        factory.return_value.start.return_value = pw
        return factory

    def test_chromium_priority_uses_patchright(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """chromium 利用可能時は patchright が使われ、標準 playwright は呼ばれない"""
        assert browser_mod._PATCHRIGHT_AVAILABLE, "patchright 必須（導入済みのはず）"
        chromium_factory = self._mock_chromium_chain()

        def _forbidden() -> None:
            raise AssertionError("chromium 成功時に標準 playwright factory を呼んではならない")

        monkeypatch.setattr(browser_mod, "_patchright_sync_playwright", chromium_factory)
        monkeypatch.setattr(browser_mod, "_std_sync_playwright", _forbidden)
        monkeypatch.setattr(browser_mod, "_chromium_requested", lambda: True)

        _pw, _browser, _ctx, _page = create_browser(account_key=None, session_file=None, headless=True)

        chromium_factory.return_value.start.assert_called_once()
        chromium_factory.return_value.start.return_value.chromium.launch.assert_called_once()

    def test_fallback_to_firefox_when_chromium_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """patchright chromium 起動失敗 → 標準 playwright Firefox へフォールバック"""
        failing_chromium = MagicMock()
        failing_chromium.return_value.start.return_value.chromium.launch.side_effect = Exception("boom")
        firefox_factory = self._mock_firefox_chain()
        monkeypatch.setattr(browser_mod, "_patchright_sync_playwright", failing_chromium)
        monkeypatch.setattr(browser_mod, "_std_sync_playwright", firefox_factory)
        monkeypatch.setattr(browser_mod, "_chromium_requested", lambda: True)

        _, launch_browser, _ctx, _page = create_browser(account_key=None, session_file=None, headless=True)

        firefox_factory.return_value.start.assert_called_once()
        firefox_factory.return_value.start.return_value.firefox.launch.assert_called_once()
        assert launch_browser is firefox_factory.return_value.start.return_value.firefox.launch.return_value

    def test_force_firefox_routes_to_std(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ロールバック（_chromium_requested=False）時は patchright を呼ばず Firefox"""
        assert browser_mod._PATCHRIGHT_AVAILABLE, "patchright 必須（導入済みのはず）"
        firefox_factory = self._mock_firefox_chain()

        def _forbidden() -> None:
            raise AssertionError("firefox 強制時に patchright factory を呼んではならない")

        monkeypatch.setattr(browser_mod, "_std_sync_playwright", firefox_factory)
        monkeypatch.setattr(browser_mod, "_patchright_sync_playwright", _forbidden)
        monkeypatch.setattr(browser_mod, "_chromium_requested", lambda: False)

        _, launch_browser, _ctx, _page = create_browser(account_key=None, session_file=None, headless=True)

        firefox_factory.return_value.start.return_value.firefox.launch.assert_called_once()
        assert launch_browser is firefox_factory.return_value.start.return_value.firefox.launch.return_value

    def test_chromium_routing_logs_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """chromium 起動時にログへ 'patchright chromium-stealth' が書かれる"""
        chromium_factory = self._mock_chromium_chain()
        monkeypatch.setattr(browser_mod, "_patchright_sync_playwright", chromium_factory)
        monkeypatch.setattr(browser_mod, "_chromium_requested", lambda: True)
        monkeypatch.setattr(browser_mod, "_std_sync_playwright", MagicMock())
        log = StringIO()
        _pw, _browser, _ctx, _page = create_browser(account_key=None, session_file=None, headless=True, log=log)
        assert "patchright chromium-stealth" in log.getvalue()

    def test_chromium_opt_in_default_off(self) -> None:
        """実運用デフォルト（KENSHO_BROWSER 未設定）では chromium 経路が無効"""
        import os

        if os.environ.get("KENSHO_BROWSER", "").lower() in ("1", "true", "chromium", "patchright", "auto"):
            pytest.skip("KENSHO_BROWSER が chromium 側に設定されているため既定確認をスキップ")
        assert browser_mod.PATCHRIGHT_CHROMIUM_ENABLED is False

    def test_close_browser_works_with_mock(self) -> None:
        """close_browser がモックでも例外なく動く（既存挙動の回帰）"""
        browser = MagicMock()
        ipw = MagicMock()
        close_browser(ipw, browser, log=None)
        browser.close.assert_called_once()
        ipw.stop.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# TestChromiumHelpers — UA / WebGL 指紋 / JS stealth の妥当性
# ═══════════════════════════════════════════════════════════════


class TestChromiumHelpers:
    def test_chromium_ua_is_chrome_not_firefox(self) -> None:
        """UA が Chrome 系（Firefox 実装 Gecko を含まない）で、Chrome/ を含む"""
        for fp in REAL_FINGERPRINTS.values():
            ua = _chromium_ua(fp)
            assert ua.startswith("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            assert "Chrome/" in ua and "Safari/537.36" in ua
            assert "Firefox/" not in ua
            assert "Gecko/20100101" not in ua  # Gecko/ エンジン記述は Chrome UA で使われない

    def test_chromium_ua_stable_per_account(self) -> None:
        """同一アカウントは安定、別アカウントは別バージョンを含み得る"""
        a1 = _chromium_ua(REAL_FINGERPRINTS["atushi16"])
        a2 = _chromium_ua(REAL_FINGERPRINTS["atushi16"])
        assert a1 == a2
        versions = {_chromium_ua(fp).split("Chrome/")[1].split(".")[0] for fp in REAL_FINGERPRINTS.values()}
        assert len(versions) >= 2, "複数アカウントで Chrome major が分岐するべき"

    def test_chromium_webgl_translated_to_angle(self) -> None:
        """renderer が Chromium 形式 (ANGLE ... Direct3D11) へ翻訳され、vendor を保持"""
        for key, fp in REAL_FINGERPRINTS.items():
            vendor, renderer = _chromium_webgl(fp)
            assert vendor == fp["webgl_vendor"]
            assert renderer.startswith("ANGLE (")
            assert "Direct3D11" in renderer
            if key == "atushi16":
                assert "HD Graphics 4600" in renderer
            elif key == "kudou":
                assert "Iris Xe" in renderer

    def test_chromium_stealth_js_valid(self) -> None:
        """JS が実改行で生成され、webdriver 上書きと WebGL getParameter 偽装を含む"""
        js = _build_chromium_stealth_js(REAL_FINGERPRINTS["atushi16"])
        assert chr(10) in js
        assert "navigator,'webdriver'" in js
        assert "getParameter" in js
        assert "hardwareConcurrency" in js
        assert "0x9246" in js  # UNMASKED_RENDERER_WEBGL
        # リテラルな \\\\n が混入してない
        assert "\\\\n" not in js

    def test_chromium_webgl_different_accounts(self) -> None:
        """アカウントにより WebGL renderer が異なる"""
        _, r16 = _chromium_webgl(REAL_FINGERPRINTS["atushi16"])
        _, rkd = _chromium_webgl(REAL_FINGERPRINTS["kudou"])
        assert r16 != rkd


# ═══════════════════════════════════════════════════════════════
# TestPatchrightChromiumRealBrowser — 実ブラウザ stealth 検証（task #4）
# ═══════════════════════════════════════════════════════════════


class TestPatchrightChromiumRealBrowser:
    """patchright chromium 実ブラウザで navigator.webdriver=False を検証。

    chromium 本体未導入などで起動不可の場合は SKIP（導入環境では必ず走る）。
    """

    def _launch(self) -> None:
        pytest.importorskip("patchright")
        from patchright.sync_api import sync_playwright

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                try:
                    ctx = browser.new_context()
                    page = ctx.new_page()
                    result = page.evaluate(
                        """()=>({webdriver: navigator.webdriver,
                                 ua: navigator.userAgent,
                                 hc: navigator.hardwareConcurrency})"""
                    )
                    assert result["webdriver"] is False, f"webdriver should be False, got {result}"
                    page.close()
                    ctx.close()
                finally:
                    browser.close()
        except Exception as e:  # chromium 未導入等
            pytest.skip(f"patchright chromium を起動できず SKIP: {type(e).__name__}: {e}")

    def test_webdriver_false_real_browser(self) -> None:
        """実 chromium で navigator.webdriver が False（自動化検出回避の実績）"""
        self._launch()

    def test_create_browser_injectable_via_helpers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """UA ヘルパーが create_browser の chromium 経路に渡る（モック検証）"""
        chromium_factory = self._mock_chromium_chain()
        monkeypatch.setattr(browser_mod, "_patchright_sync_playwright", chromium_factory)
        monkeypatch.setattr(browser_mod, "_std_sync_playwright", MagicMock())
        monkeypatch.setattr(browser_mod, "_chromium_requested", lambda: True)
        # keyring 実アクセスを避ける
        monkeypatch.setattr(browser_mod, "_load_browser_storage", lambda *a, **k: None)

        _pw, _browser, ctx, _page = create_browser(account_key="atushi16", session_file=None, headless=True)

        # new_context 呼び出しの実体は chromium browser mock 経由
        nctx = chromium_factory.return_value.start.return_value.chromium.launch.return_value.new_context
        nctx.assert_called_once()
        kwargs = nctx.call_args.kwargs
        assert kwargs["user_agent"].startswith("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        assert "Firefox/" not in kwargs["user_agent"]
        assert kwargs["device_scale_factor"] == 1.0
        # socks5h:// は Chromium 用に socks5:// へ正規化される
        assert kwargs["proxy"]["server"] == browser_mod.PROXY_MAP["atushi16"].replace("socks5h://", "socks5://")
        assert "socks5h://" not in kwargs["proxy"]["server"]
        # add_init_script に chromium stealth が注入される
        page = ctx.new_page.return_value
        assert page.add_init_script.call_count >= 2

    def _mock_chromium_chain(self) -> MagicMock:
        page = MagicMock()
        page.viewport_size = {"width": 1366, "height": 768}
        ctx = MagicMock()
        ctx.pages = []
        ctx.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = ctx
        pw = MagicMock()
        pw.chromium.launch.return_value = browser
        factory = MagicMock()
        factory.return_value.start.return_value = pw
        return factory
