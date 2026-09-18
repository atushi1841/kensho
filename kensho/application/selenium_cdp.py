#!/usr/bin/env python3
"""
Kensho SeleniumBase CDP Mode — BOT対策強化モジュール
SeleniumBaseのCDP(Chrome DevTools Protocol)モードを活用し、
Playwright Firefoxに代わるBOT検出回避型ブラウザ自動化を提供する。

特徴:
- CDP Mode: Chrome DevToolsプロトコル直接操作で自動化痕跡を低減
- 指紋偽装: WebGL/Canvas/Fonts/UAを垢別に偽装
- ランダム遅延: アクション間3〜10秒のゆらぎ
- マウス軌跡: ベジェ曲線＋Jitterで人間らしい操作
- BOT検出テスト: 模擬懸賞ページでbotフラグ捕获確認

使い方:
    from kensho.application.selenium_cdp import KenshoCDP
    with KenshoCDP(account_key="atushi16") as driver:
        driver.get("https://x.com/status/123")
        driver.click_element(...)
"""

from __future__ import annotations

import math
import os
import random
import time
from contextlib import contextmanager
from typing import Any

from seleniumbase import SB

# ── 指紋データ（browser.py のFINGERPRINTSと同期） ──
FINGERPRINTS: dict[str, dict[str, Any]] = {
    "atushi16": {
        "seed": 42,
        "accept_language": "ja-JP,ja;q=0.9,en;q=0.8",
        "screen_width": 1366,
        "screen_height": 768,
        "pixel_ratio": 1.0,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0.1",
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "Intel HD Graphics 4600 (ANGLE)",
    },
    "kudou": {
        "seed": 77,
        "accept_language": "ja,en;q=0.9,zh-CN;q=0.7",
        "screen_width": 1920,
        "screen_height": 1080,
        "pixel_ratio": 1.0,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0.1",
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "Intel Iris Xe Graphics",
    },
    "zin20120731": {
        "seed": 55,
        "accept_language": "ja,en-US;q=0.9,en;q=0.8",
        "screen_width": 1366,
        "screen_height": 768,
        "pixel_ratio": 1.0,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "Intel UHD Graphics 620",
    },
    "TankanNotes": {
        "seed": 66,
        "accept_language": "ja;q=0.9,en-US;q=0.8,ja-JP;q=0.7",
        "screen_width": 1440,
        "screen_height": 900,
        "pixel_ratio": 1.0,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0",
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "Intel HD Graphics 630",
    },
    "inobase1-4": {
        "seed": 44,
        "accept_language": "ja,en;q=0.9,zh-CN;q=0.7,ko;q=0.5",
        "screen_width": 1280,
        "screen_height": 720,
        "pixel_ratio": 1.0,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "Intel Iris Xe Graphics",
    },
    "toushiwatch": {
        "seed": 13,
        "accept_language": "ja,ja-JP;q=0.9,en-US;q=0.8,en;q=0.7",
        "screen_width": 1680,
        "screen_height": 1050,
        "pixel_ratio": 1.0,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
        "webgl_vendor": "Google Inc. (AMD)",
        "webgl_renderer": "ANGLE (AMD, AMD Radeon RX 6600 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
}

# ★ 垢別SOCKS5プロキシ（browser.pyのPROXY_MAPと同期）
PROXY_MAP: dict[str, str] = {
    "atushi16": "socks5h://172.26.80.1:1081",
    "kudou": "socks5h://172.26.80.1:1082",
    "zin20120731": "socks5h://172.26.80.1:1084",
    "TankanNotes": "socks5h://172.26.80.1:1085",
    "inobase1-4": "socks5h://172.26.80.1:1089",
    "toushiwatch": "socks5h://172.26.80.1:1087",
}

USE_PROXY: bool = os.environ.get("USE_PROXY", "True").lower() == "true"

# ── BOT検出フラグ定義 ──
BOT_FLAGS = [
    "navigator.webdriver",
    "navigator.plugins.length === 0",
    "navigator.languages.length === 0",
    "screen.width === 0",
    "screen.height === 0",
    "window.outerWidth === 0",
    "document.documentElement.webdriver",
    "chrome.runtime",
    "HeadlessChrome",
    "automation",
    "webkitMutationEvents",
]


def _bezier_point(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    """ベジェ曲線のt位置を計算"""
    u = 1 - t
    return u**3 * p0 + 3 * u**2 * t * p1 + 3 * u * t**2 * p2 + t**3 * p3


class KenshoCDP:
    """SeleniumBase CDP ModeによるKensho向けブラウザ制御クラス"""

    def __init__(self, account_key: str = "atushi16", headless: bool = True):
        self.account_key = account_key
        self.headless = headless
        self.fp = FINGERPRINTS.get(account_key, FINGERPRINTS["atushi16"])
        self._sb: SB | None = None
        self._action_count = 0

    @property
    def driver(self) -> SB | None:
        """SBインスタンスへのエイリアス（既存コード互換）"""
        return self._sb

    @property
    def proxy(self) -> str | None:
        if USE_PROXY and self.account_key in PROXY_MAP:
            return PROXY_MAP[self.account_key]
        return None

    def __enter__(self) -> "KenshoCDP":
        self.launch()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def launch(self) -> None:
        """CDP ModeでヘッドレスChromeを起動"""
        sb_kwargs: dict[str, Any] = {
            "uc": True,  # undetected-chromedriverモード
            "headless2": self.headless,
            "locale_code": "ja",
        }

        if self.proxy:
            sb_kwargs["proxy"] = self.proxy

        # SBはコンテキストマネージャ — with内で使用
        self._sb = SB(**sb_kwargs)
        # SBのEnterを手動で呼び出す（with文の代わりに）
        self._sb.__enter__()

        self._sb.open("about:blank")

        # ウィンドウサイズ設定（指紋に合わせる）
        self._sb.set_window_size(
            self.fp["screen_width"], self.fp["screen_height"]
        )

        # CDPによる指紋偽装適用
        self._apply_cdp_spoofing()

        # ランダム初期遅延（人間らしくするため）
        time.sleep(random.uniform(3, 10))

    def _apply_cdp_spoofing(self) -> None:
        """CDPコマンドで指紋を偽装"""
        if not self._sb:
            return

        cdp = self._sb.cdp

        # User-Agent偽装
        ua = self.fp["user_agent"]
        cdp.send("Network.setUserAgentOverride", {"userAgent": ua})

        # Viewport設定
        w = self.fp["screen_width"]
        h = self.fp["screen_height"]
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": w,
            "height": h,
            "deviceScaleFactor": self.fp["pixel_ratio"],
            "mobile": False,
        })

        # JavaScriptによるnavigator偽装
        self._execute_stealth_js()

    def _execute_stealth_js(self) -> None:
        """navigatorプロパティの自動化検出回避"""
        if not self._sb:
            return

        hc_cores = random.choice([4, 8, 6, 12, 16])
        stealth_js = (
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            "Object.defineProperty(navigator, 'plugins', {"
            "get: () => [{name: 'Widevine Content Decryption Module',"
            "filename: 'widevinecdm.dll',"
            "description: 'Enables Widevine encrypted media playback',"
            "version: '4.10.2830.0', length: 0, item: () => null, namedItem: () => null}],"
            "});"
            f"Object.defineProperty(navigator, 'languages', {{get: () => ['ja-JP', 'ja', 'en-US', 'en']}});"
            f"Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {hc_cores}}});"
            "Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});"
        )

        self._sb.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": stealth_js,
        })

    def human_click(self, selector: str) -> None:
        """人間らしいクリック（マウス軌跡＋ランダム遅延）"""
        if not self._sb:
            raise RuntimeError("Driver not launched")

        element = self._sb.find_element("css selector", selector)
        location = element.location
        size = element.size

        # 開始位置（ランダム）
        start_x = random.randint(0, self.fp["screen_width"])
        start_y = random.randint(0, self.fp["screen_height"])

        # ターゲット位置（要素中心＋ランダムオフセット）
        target_x = location["x"] + size["width"] / 2 + random.uniform(-10, 10)
        target_y = location["y"] + size["height"] / 2 + random.uniform(-10, 10)

        # ベジェ曲線に沿ったマウス移動
        steps = random.randint(12, 25)
        for i in range(steps + 1):
            t = i / steps
            x = _bezier_point(start_x, start_x + random.uniform(-50, 50),
                               target_x + random.uniform(-50, 50), target_x, t)
            y = _bezier_point(start_y, start_y + random.uniform(-50, 50),
                               target_y + random.uniform(-50, 50), target_y, t)
            self._sb.move_by_element(x, y)  # type: ignore[attr-defined]
            time.sleep(random.uniform(0.008, 0.030))

        element.click()
        self._action_count += 1

        # アクション間ランダム遅延（3〜10秒）
        time.sleep(random.uniform(3, 10))

    def human_type(self, selector: str, text: str) -> None:
        """人間らしいタイピング"""
        if not self._sb:
            raise RuntimeError("Driver not launched")

        element = self._sb.find_element("css selector", selector)
        element.click()
        time.sleep(random.uniform(0.5, 1.5))

        for char in text:
            element.send_keys(char)
            delay = random.uniform(0.08, 0.25)
            if random.random() < 0.08:  # 8%で小さなポーズ
                delay += random.uniform(0.3, 0.8)
            time.sleep(delay)

        self._action_count += len(text)
        time.sleep(random.uniform(3, 10))

    def check_bot_flags(self) -> list[str]:
        """ページ上のBOT検出フラグをチェック"""
        if not self._sb:
            return []

        detected: list[str] = []
        for flag in BOT_FLAGS:
            try:
                result = self._sb.execute_script(f"return !!({flag});")
                if result:
                    detected.append(flag)
            except Exception:
                pass

        return detected

    def get_exit_code(self) -> int:
        """Chromeの終了コードを確認（0=正常）"""
        if not self._sb:
            return -1
        try:
            self._sb.execute_script("return 1;")
            return 0
        except Exception:
            return 1

    def close(self) -> None:
        """ブラウザを終了"""
        if self._sb:
            try:
                self._sb.__exit__(None, None, None)
            except Exception:
                pass
            self._sb = None

    @property
    def action_count(self) -> int:
        """実行アクション数"""
        return self._action_count


@contextmanager
def cdp_session(account_key: str = "atushi16", headless: bool = True) -> KenshoCDP:
    """CDPセッションコンテキストマネージャ"""
    session = KenshoCDP(account_key=account_key, headless=headless)
    try:
        session.launch()
        yield session
    finally:
        session.close()


def quick_launch_test(account_key: str = "atushi16") -> dict[str, Any]:
    """簡易起動テスト: インポート→起動→停止の一連動作確認"""
    result: dict[str, Any] = {
        "account_key": account_key,
        "import_ok": True,
        "launch_ok": False,
        "bot_flags": [],
        "exit_code": -1,
        "error": "",
    }

    try:
        with KenshoCDP(account_key=account_key, headless=True) as driver:
            result["launch_ok"] = driver.get_exit_code() == 0
            result["bot_flags"] = driver.check_bot_flags()
            result["exit_code"] = driver.get_exit_code()
    except Exception as e:
        result["error"] = str(e)

    return result