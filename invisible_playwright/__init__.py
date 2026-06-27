"""
invisible_playwright — Pure-Python Playwright 互換モジュール

オリジナルは C++ レベル指紋偽装パッケージ（プライベート）。
この代替モジュールは Playwright の組み込み stealth 設定で代用する。
Linux/WSL 環境向け（Firefox + 日本語ロケール）。
"""

from __future__ import annotations

import random
from typing import Any

from playwright.sync_api import Browser, sync_playwright

__all__ = ["InvisiblePlaywright"]

# 固定ビューポートサイズ一覧（seed モード選択用）
VIEWPORTS: list[tuple[int, int]] = [
    (1366, 768),
    (1440, 900),
    (1536, 864),
    (1600, 900),
    (1680, 1050),
    (1920, 1080),
    (1920, 1200),
]


class InvisiblePlaywright:
    """Playwright Firefox ブラウザを stealth 設定でラップするコンテキストマネージャ。

    Parameters
    ----------
    seed : int or None
        再現可能な指紋設定用シード値。
        None の場合、起動ごとにランダムなビューポートが選ばれる。
        整数の場合、seed % 7 で VIEWPORTS から決定。
    headless : bool
        Firefox をヘッドレスモードで起動するか（デフォルト True）。
    """

    def __init__(self, seed: int | None = None, headless: bool = True,
                 extra_prefs: dict[str, Any] | None = None) -> None:
        self.seed = seed
        self.headless = headless
        self.extra_prefs = extra_prefs or {}
        self._playwright: Any = None
        self._browser: Browser | None = None

    def _pick_viewport(self) -> tuple[int, int]:
        """seed に基づいてビューポートサイズを決定する。"""
        if self.seed is None:
            return random.choice(VIEWPORTS)
        return VIEWPORTS[self.seed % 7]

    def _stealth_script(self, viewport: tuple[int, int],
                        webgl_vendor: str = "Google Inc. (Intel)",
                        webgl_renderer: str = "Intel Iris OpenGL Engine") -> str:
        """navigator.webdriver を隠蔽し、言語・プラットフォームを偽装する。

        日本語ロケール（ja-JP, ja）を設定し、
        WebDriver 検出を回避するための初期化スクリプト。
        """
        width, height = viewport

        # プラットフォームの選択: Linux環境でもWin32を偽装
        platform_override = "Win32"

        return f"""
        // ── navigator.webdriver を undefined に ──
        Object.defineProperty(navigator, 'webdriver', {{
            get: () => undefined,
            configurable: true,
        }});

        // ── 言語設定（日本語優先） ──
        Object.defineProperty(navigator, 'languages', {{
            get: () => ['ja-JP', 'ja'],
            configurable: true,
        }});
        Object.defineProperty(navigator, 'language', {{
            get: () => 'ja-JP',
            configurable: true,
        }});

        // ── プラットフォーム偽装 ──
        Object.defineProperty(navigator, 'platform', {{
            get: () => '{platform_override}',
            configurable: true,
        }});

        // ── 画面サイズをビューポートに合わせる ──
        Object.defineProperty(screen, 'width', {{
            get: () => {width},
            configurable: true,
        }});
        Object.defineProperty(screen, 'height', {{
            get: () => {height},
            configurable: true,
        }});
        Object.defineProperty(screen, 'availWidth', {{
            get: () => {width},
            configurable: true,
        }});
        Object.defineProperty(screen, 'availHeight', {{
            get: () => {height},
            configurable: true,
        }});

        // ── ハードウェア並列性 ──
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: () => 8,
            configurable: true,
        }});

        // ── プラグイン偽装 ──
        const fakePlugins = [
            {{ name: "Shockwave Flash", filename: "libflashplayer.so", description: "Shockwave Flash 35.0 r0" }},
            {{ name: "Widevine Content Decryption Module", filename: "libwidevinecdm.so", description: "Widevine Content Decryption Module" }},
            {{ name: "OpenH264 Video Codec", filename: "libopenh264.so", description: "OpenH264 Video Codec provided by Cisco" }},
            {{ name: "Microsoft Teams Media", filename: "libmsteamsmedia.so", description: "Microsoft Teams Media" }},
        ];
        Object.defineProperty(navigator, 'plugins', {{
            get: () => fakePlugins,
            configurable: true,
        }});
        Object.defineProperty(navigator, 'mimeTypes', {{
            get: () => [].constructor.prototype,
            configurable: true,
        }});

        // ── maxTouchPoints（デスクトップは0） ──
        Object.defineProperty(navigator, 'maxTouchPoints', {{
            get: () => 0,
            configurable: true,
        }});

        // ── WebGL Vendor/Renderer 偽装（アカウント別） ──
        const WGL_VENDOR = {webgl_vendor};
        const WGL_RENDERER = {webgl_renderer};
        const origGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(param) {{
            if (param === 37445) return WGL_VENDOR;
            if (param === 37446) return WGL_RENDERER;
            return origGetParameter.call(this, param);
        }};

        // ── Canvas フィンガープリント対策（toDataURLに微小ノイズ） ──
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(...args) {{
            const base64 = origToDataURL.apply(this, args);
            if (base64.length > 100) {{
                const pos = Math.floor(Math.random() * 10) + 50;
                const noise = Math.random() > 0.5 ? "A" : "B";
                return base64.substring(0, pos) + noise + base64.substring(pos + 1);
            }}
            return base64;
        }};

        // ── スタックトレース検出対策（Error.stack に現実的なフレームを追加） ──
        const OrigError = Error;
        Error = function(msg, file, line, col) {{
            const e = new OrigError(msg, file, line, col);
            const origStack = e.stack || '';
            if (origStack.includes('__puppeteer') || origStack.includes('playwright') || origStack.includes('__driver__')) {{
                Object.defineProperty(e, 'stack', {{
                    get: () => origStack.replace(/__puppeteer__[^\\n]*/g, 'evalcode@chrome://').replace(/playwright/g, ''),
                    configurable: true,
                }});
            }}
            return e;
        }};
        Error.prototype = OrigError.prototype;
        // Error.captureStackTrace を維持
        if (OrigError.captureStackTrace) {{
            Error.captureStackTrace = OrigError.captureStackTrace;
        }}""
        """

    def __enter__(self) -> Browser:
        """コンテキストに入り、Firefox ブラウザを起動して返す。

        Returns
        -------
        playwright.sync_api.Browser
            Firefox ブラウザインスタンス（stealth 設定済み）。
        """
        viewport = self._pick_viewport()
        ext_vendor = self.extra_prefs.pop('_webgl_vendor', "Google Inc. (Intel)")
        ext_renderer = self.extra_prefs.pop('_webgl_renderer', "Intel Iris OpenGL Engine")

        self._playwright = sync_playwright().start()
        base_prefs: dict[str, Any] = {
            "media.peerconnection.enabled": False,
            "privacy.resistFingerprinting": True,
            "privacy.trackingprotection.fingerprinting.enabled": True,
            "general.platform.override": "Win32",
            "general.oscpu.override": "Windows NT 10.0",
        }
        base_prefs.update(self.extra_prefs)
        self._browser = self._playwright.firefox.launch(
            headless=self.headless,
            channel=None,  # Linux/WSL では不要
            firefox_user_prefs=base_prefs,
        )

        # コンテキスト（stealth 設定を加えた新規セッション）を作成
        context = self._browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )

        # 各ページに stealth スクリプトを注入
        context.add_init_script(
            self._stealth_script(viewport, ext_vendor, ext_renderer)
        )

        return self._browser

    def __exit__(self, *args: Any) -> None:
        """コンテキストを抜け、Playwright リソースを解放する。"""
        try:
            if self._browser is not None:
                self._browser.close()
                self._browser = None
        finally:
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
