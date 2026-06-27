"""invisible_playwright モジュールの単体テスト"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


from invisible_playwright import InvisiblePlaywright


class TestInvisiblePlaywrightInit:
    """InvisiblePlaywright コンストラクタのテスト"""

    def test_default_parameters(self) -> None:
        """デフォルト: seed=None, headless=True"""
        ipw = InvisiblePlaywright()
        assert ipw.seed is None
        assert ipw.headless is True

    def test_seed_int(self) -> None:
        """seed に整数を与える"""
        ipw = InvisiblePlaywright(seed=42)
        assert ipw.seed == 42
        assert ipw.headless is True

    def test_headless_false(self) -> None:
        """headless=False"""
        ipw = InvisiblePlaywright(headless=False)
        assert ipw.headless is False

    def test_seed_and_headless(self) -> None:
        """両方指定"""
        ipw = InvisiblePlaywright(seed=77, headless=False)
        assert ipw.seed == 77
        assert ipw.headless is False


class TestViewportSelection:
    """ビューポート選択ロジックのテスト"""

    VIEWPORTS = [
        (1366, 768),
        (1440, 900),
        (1536, 864),
        (1600, 900),
        (1680, 1050),
        (1920, 1080),
        (1920, 1200),
    ]

    def test_seed_0(self) -> None:
        assert InvisiblePlaywright(seed=0)._pick_viewport() == (1366, 768)

    def test_seed_1(self) -> None:
        assert InvisiblePlaywright(seed=1)._pick_viewport() == (1440, 900)

    def test_seed_2(self) -> None:
        assert InvisiblePlaywright(seed=2)._pick_viewport() == (1536, 864)

    def test_seed_3(self) -> None:
        assert InvisiblePlaywright(seed=3)._pick_viewport() == (1600, 900)

    def test_seed_4(self) -> None:
        assert InvisiblePlaywright(seed=4)._pick_viewport() == (1680, 1050)

    def test_seed_5(self) -> None:
        assert InvisiblePlaywright(seed=5)._pick_viewport() == (1920, 1080)

    def test_seed_6(self) -> None:
        assert InvisiblePlaywright(seed=6)._pick_viewport() == (1920, 1200)

    def test_seed_7_wraps(self) -> None:
        """seed=7 → 7%7=0 → 最初のビューポート"""
        assert InvisiblePlaywright(seed=7)._pick_viewport() == (1366, 768)

    def test_seed_negative(self) -> None:
        """負のシード → Python の % は正数を返すので動作"""
        vp = InvisiblePlaywright(seed=-1)._pick_viewport()
        assert vp in [
            (1366, 768),
            (1440, 900),
            (1536, 864),
            (1600, 900),
            (1680, 1050),
            (1920, 1080),
            (1920, 1200),
        ]

    def test_seed_none_random(self) -> None:
        """seed=None はランダム選択（VIEWPORTS 内であることのみ確認）"""
        vp = InvisiblePlaywright(seed=None)._pick_viewport()
        assert vp in [
            (1366, 768),
            (1440, 900),
            (1536, 864),
            (1600, 900),
            (1680, 1050),
            (1920, 1080),
            (1920, 1200),
        ]


class TestStealthScript:
    """stealth スクリプト生成のテスト"""

    FIREFOX_PREFS = {
        "media.peerconnection.enabled": False,
        "privacy.resistFingerprinting": True,
        "privacy.trackingprotection.fingerprinting.enabled": True,
        "general.platform.override": "Win32",
        "general.oscpu.override": "Windows NT 10.0",
    }

    def test_webdriver_undefined(self) -> None:
        """navigator.webdriver → undefined"""
        script = InvisiblePlaywright(seed=0)._stealth_script((1366, 768))
        assert "webdriver" in script
        assert "undefined" in script

    def test_languages_ja(self) -> None:
        """言語設定は ja-JP / ja"""
        script = InvisiblePlaywright(seed=1)._stealth_script((1440, 900))
        assert "ja-JP" in script

    def test_platform_linux(self) -> None:
        '''全環境で platform は Win32（常時偽装）'''
        script = InvisiblePlaywright(seed=0)._stealth_script((1366, 768))
        assert 'Win32' in script
        assert 'Linux x86_64' not in script

    def test_platform_win32(self) -> None:
        '''Win32 環境（WSL外）でも Win32'''
        script = InvisiblePlaywright(seed=0)._stealth_script((1366, 768))
        assert 'Win32' in script

    def test_viewport_in_script(self) -> None:
        """ビューポート値がスクリプトに反映される"""
        script = InvisiblePlaywright(seed=5)._stealth_script((1920, 1080))
        assert "1920" in script
        assert "1080" in script

    def test_hardware_concurrency(self) -> None:
        """hardwareConcurrency の偽装がある"""
        script = InvisiblePlaywright(seed=0)._stealth_script((1920, 1080))
        assert "hardwareConcurrency" in script
        assert "8" in script

    def test_plugins_fake(self) -> None:
        """プラグイン偽装がある"""
        script = InvisiblePlaywright(seed=0)._stealth_script((1920, 1080))
        assert "fakePlugins" in script
        assert "Shockwave Flash" in script

    def test_max_touch_points(self) -> None:
        """maxTouchPoints の偽装がある"""
        script = InvisiblePlaywright(seed=0)._stealth_script((1920, 1080))
        assert "maxTouchPoints" in script

    def test_webgl_fake(self) -> None:
        """WebGL vendor/renderer の偽装がある"""
        script = InvisiblePlaywright(seed=0)._stealth_script((1920, 1080))
        assert "getParameter" in script
        assert "Intel Iris" in script

    def test_canvas_noise(self) -> None:
        """Canvas toDataURL ノイズ注入がある"""
        script = InvisiblePlaywright(seed=0)._stealth_script((1920, 1080))
        assert "toDataURL" in script
        assert "origToDataURL" in script


class TestContextManagerProtocol:
    """__enter__ / __exit__ プロトコルのテスト（モック使用）"""

    FIREFOX_PREFS = {
        "media.peerconnection.enabled": False,
        "privacy.resistFingerprinting": True,
        "privacy.trackingprotection.fingerprinting.enabled": True,
        "general.platform.override": "Win32",
        "general.oscpu.override": "Windows NT 10.0",
    }

    @patch("invisible_playwright.sync_playwright")
    def test_enter_returns_browser(self, mock_sp: MagicMock) -> None:
        """__enter__ が Browser を返す"""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.firefox.launch.return_value = mock_browser
        mock_sp.return_value.start.return_value = mock_playwright

        ipw = InvisiblePlaywright(seed=0, headless=True)
        result = ipw.__enter__()

        assert result is mock_browser
        mock_sp.return_value.start.assert_called_once()
        mock_playwright.firefox.launch.assert_called_once_with(
            headless=True, channel=None, firefox_user_prefs=self.FIREFOX_PREFS,
        )

    @patch("invisible_playwright.sync_playwright")
    def test_enter_creates_context_with_init_script(self, mock_sp: MagicMock) -> None:
        """__enter__ がコンテキスト作成 + stealth スクリプト注入"""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_playwright.firefox.launch.return_value = mock_browser
        mock_sp.return_value.start.return_value = mock_playwright

        ipw = InvisiblePlaywright(seed=1, headless=True)
        ipw.__enter__()

        mock_browser.new_context.assert_called_once()
        call_kwargs = mock_browser.new_context.call_args.kwargs
        assert call_kwargs["viewport"] == {"width": 1440, "height": 900}
        assert call_kwargs["locale"] == "ja-JP"
        assert call_kwargs["timezone_id"] == "Asia/Tokyo"

        mock_context.add_init_script.assert_called_once()

    @patch("invisible_playwright.sync_playwright")
    def test_exit_closes_browser_and_stops_playwright(
        self, mock_sp: MagicMock
    ) -> None:
        """__exit__ がブラウザと Playwright をクリーンアップ"""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.firefox.launch.return_value = mock_browser
        mock_sp.return_value.start.return_value = mock_playwright

        ipw = InvisiblePlaywright(seed=0)
        ipw.__enter__()
        ipw.__exit__(None, None, None)

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()

    @patch("invisible_playwright.sync_playwright")
    def test_exit_without_enter(self, mock_sp: MagicMock) -> None:
        """__enter__ なしで __exit__ してもエラーにならない"""
        ipw = InvisiblePlaywright(seed=0)
        # __enter__ を呼ばずに __exit__ を直接呼ぶ
        ipw.__exit__(None, None, None)  # 例外が発生しないこと
        mock_sp.assert_not_called()

    @patch("invisible_playwright.sync_playwright")
    def test_headless_false_propagates(self, mock_sp: MagicMock) -> None:
        """headless=False が firefox.launch() に伝播"""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.firefox.launch.return_value = mock_browser
        mock_sp.return_value.start.return_value = mock_playwright

        ipw = InvisiblePlaywright(seed=0, headless=False)
        ipw.__enter__()

        mock_playwright.firefox.launch.assert_called_once_with(
            headless=False, channel=None, firefox_user_prefs=self.FIREFOX_PREFS,
        )

    @patch("invisible_playwright.sync_playwright")
    def test_channel_is_none(self, mock_sp: MagicMock) -> None:
        """channel=None が firefox.launch() に渡される（Linux/WSL）"""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.firefox.launch.return_value = mock_browser
        mock_sp.return_value.start.return_value = mock_playwright

        ipw = InvisiblePlaywright(seed=0)
        ipw.__enter__()

        mock_playwright.firefox.launch.assert_called_once_with(
            headless=True, channel=None, firefox_user_prefs=self.FIREFOX_PREFS,
        )
