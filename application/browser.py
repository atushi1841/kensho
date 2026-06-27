"""
Kensho Browser — invisible_playwright Firefox ブラウザ制御
v4.0: C++レベル指紋偽装（invisible_playwright）+ アカウント別シード
"""
from __future__ import annotations

import asyncio
import os
import time
import random
import json
from typing import Any

# ═══════════════════════════════════════════════════════════
# 垢別ブラウザ指紋コンセプト（固定シード値）
# invisible_playwright はC++レベルで偽装するため、
# ここでは reproduce 用のシードと画面解像度のみ管理。
# ═══════════════════════════════════════════════════════════
FINGERPRINTS: dict[str, dict[str, Any]] = {
    'atushi16': {
        'seed': 42,
        'screen_width': 1366,
        'screen_height': 768,
        'pixel_ratio': 1.0,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
        'webgl_vendor': 'Google Inc. (Intel)',
        'webgl_renderer': 'Intel HD Graphics 4600 (ANGLE)',
        'tls': {
            'security.tls.version.min': 3,
            'security.tls.version.max': 4,
            'security.tls.hello_downgrade': False,
            'security.ssl.enable_ocsp_stapling': True,
            'security.ssl.enable_ocsp_must_staple': False,
        },
    },
    'kudou': {
        'seed': 77,
        'screen_width': 1920,
        'screen_height': 1080,
        'pixel_ratio': 1.0,
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0',
        'webgl_vendor': 'Apple Inc.',
        'webgl_renderer': 'Apple M1',
        'tls': {
            'security.tls.version.min': 3,
            'security.tls.version.max': 4,
            'security.tls.hello_downgrade': True,
            'security.ssl.enable_ocsp_stapling': True,
            'security.ssl.enable_ocsp_must_staple': True,
        },
    },
    'atushi1840': {
        'seed': 13,
        'screen_width': 1536,
        'screen_height': 864,
        'pixel_ratio': 1.0,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
        'webgl_vendor': 'Google Inc. (NVIDIA)',
        'webgl_renderer': 'NVIDIA GeForce GTX 1060',
        'tls': {
            'security.tls.version.min': 3,
            'security.tls.version.max': 4,
            'security.tls.hello_downgrade': True,
            'security.ssl.enable_ocsp_stapling': False,
            'security.ssl.enable_ocsp_must_staple': False,
        },
    },
    'zin20120731': {
        'seed': 55,
        'screen_width': 1366,
        'screen_height': 768,
        'pixel_ratio': 1.0,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
        'webgl_vendor': 'Google Inc. (Intel)',
        'webgl_renderer': 'Intel UHD Graphics 620',
        'tls': {
            'security.tls.version.min': 3,
            'security.tls.version.max': 4,
            'security.tls.hello_downgrade': False,
            'security.ssl.enable_ocsp_stapling': True,
            'security.ssl.enable_ocsp_must_staple': True,
        },
    },
    'TankanNotes': {
        'seed': 91,
        'screen_width': 1440,
        'screen_height': 900,
        'pixel_ratio': 1.0,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0',
        'webgl_vendor': 'Google Inc. (AMD)',
        'webgl_renderer': 'AMD Radeon RX 580',
        'tls': {
            'security.tls.version.min': 3,
            'security.tls.version.max': 4,
            'security.tls.hello_downgrade': True,
            'security.ssl.enable_ocsp_stapling': False,
            'security.ssl.enable_ocsp_must_staple': True,
        },
    },
}

# invisible_playwright は使わないが、型の互換性のためにエイリアス
# build_stealth_script は C++レベル偽装に置き換えたため削除


def random_viewport(page: Any) -> None:
    """ランダムなビューポート"""
    w: int = random.choice([1366, 1440, 1536, 1600, 1680, 1720, 1920])
    h: int = random.choice([768, 800, 864, 900, 960, 1024, 1080])
    page.set_viewport_size({'width': w, 'height': h})


def set_viewport_for_fingerprint(page: Any, fp: dict[str, Any]) -> None:
    """指紋と一致するビューポートを設定"""
    page.set_viewport_size({'width': fp['screen_width'], 'height': fp['screen_height']})


def human_like_mouse(page: Any, element: Any) -> None:
    """人間らしいマウス軌跡でクリック（ベジェ曲線）"""
    box = element.bounding_box()
    if not box:
        vp = page.viewport_size
        cx: int = vp['width'] // 2
        cy: int = vp['height'] // 2
        bx, by = element.evaluate('(el) => {const r = el.getBoundingClientRect(); return [r.x, r.y];}')
        if not bx:
            element.click()
            return
        steps: int = random.randint(10, 20)
        for i in range(steps + 1):
            t: float = i / steps
            u: float = 1 - t
            x: float = u**2 * cx + 2*u*t * (cx + (bx-cx)*0.3) + t**2 * bx
            y: float = u**2 * cy + 2*u*t * (cy + (by-cy)*0.3) + t**2 * cy
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.01, 0.03))
        page.mouse.click(bx, by)
        return
    vp = page.viewport_size
    start_x: int = random.randint(50, vp['width'] - 50)
    start_y: int = random.randint(50, vp['height'] - 50)
    end_x: float = box['x'] + box['width'] * random.uniform(0.2, 0.8)
    end_y: float = box['y'] + box['height'] * random.uniform(0.2, 0.8)
    cx1: float = start_x + (end_x - start_x) * random.uniform(0.1, 0.4)
    cy1: float = start_y + random.uniform(-100, 100)
    cx2: float = end_x + random.uniform(-100, 100)
    cy2: float = end_y + random.uniform(-50, 50)
    steps = random.randint(15, 30)
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * start_x + 3*u**2*t * cx1 + 3*u*t**2 * cx2 + t**3 * end_x
        y = u**3 * start_y + 3*u**2*t * cy1 + 3*u*t**2 * cy2 + t**3 * end_y
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.01, 0.035))
    time.sleep(random.uniform(0.05, 0.15))
    page.mouse.click(end_x, end_y)


def create_browser(account_key: str | None = None, session_file: str | None = None,
                   headless: bool = True, log: Any = None) -> tuple[Any, Any, Any, Any]:
    """
    invisible_playwright Firefox ブラウザを起動（C++レベル指紋偽装）。
    account_key が指定されていれば、垢別固定シードで指紋を再現。

    戻り値: (invisible_pw_instance, browser, context, page)
    invisible_pw_instance は close_browser() で終了処理に使う。
    """
    from invisible_playwright import InvisiblePlaywright

    if log:
        log.write(f"DEBUG: invisible_playwright Firefox starting (account={account_key})")

    # asyncio loop 残留対策: sync Playwright起動前にクリア
    try:
        asyncio.get_running_loop()
        # ループが回っている → sync Playwrightは使えない
        # （実際は発生しないはず。もし発生したらnew_event_loopで上書き）
        asyncio.set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        # ループ無し → 正常。何もしない
        pass

    # 垢別シードマッピング
    fp: dict[str, Any] | None = FINGERPRINTS.get(account_key) if account_key else None
    seed: int | None = fp['seed'] if fp else None

    # invisible_playwright インスタンス作成（まだ起動しない）
    extra_prefs: dict[str, Any] = {}
    if fp:
        wv = fp.get('webgl_vendor', 'Google Inc. (Intel)')
        wr = fp.get('webgl_renderer', 'Intel Iris OpenGL Engine')
        extra_prefs['_webgl_vendor'] = wv
        extra_prefs['_webgl_renderer'] = wr
        tls_prefs = fp.get('tls', {})
        extra_prefs.update(tls_prefs)
    ipw = InvisiblePlaywright(seed=seed, headless=headless, extra_prefs=extra_prefs)

    # コンテキストマネージャーに入る → ブラウザ起動
    browser: Any = ipw.__enter__()

    if log:
        log.write("DEBUG: Firefox browser launched (invisible_playwright)")

    # ── セッション読み込み（auth_token等）──
    storage = None
    if session_file and os.path.exists(session_file):
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                storage = json.load(f)
        except Exception as e:
            if log:
                log.write(f"WARN: session file read error: {e}")
    # keyring優先
    if account_key:
        from utils.keyring import load_session as _kr_load
        kr_data = _kr_load(account_key)
        if kr_data:
            storage = kr_data
            if log:
                log.write("  [KEYRING] Session loaded from Credential Manager")

    if fp and log:
        log.write(f"  [FINGERPRINT] {account_key}: seed={fp['seed']}")

    device_scale: float = fp['pixel_ratio'] if fp else random.choice([1.0, 1.25, 1.5])
    ctx_kwargs: dict[str, Any] = {
        'storage_state': storage,
        'locale': 'ja-JP',
        'timezone_id': 'Asia/Tokyo',
        'device_scale_factor': device_scale,
    }
    if fp:
        ctx_kwargs['user_agent'] = fp['user_agent']
    ctx = browser.new_context(**ctx_kwargs)

    # ★ invisible_playwright は C++レベルで全指紋を偽装するため、
    #    JSによる stealth_script の注入は不要！
    #    （navigator.webdriver, plugins, WebGL, Canvas, Fonts,
    #      Audio, Screen, Timezone など全てカバー済み）

    if log:
        log.write("DEBUG: context created")

    page = ctx.new_page()

    if fp:
        set_viewport_for_fingerprint(page, fp)
    else:
        random_viewport(page)

    if log:
        log.write("DEBUG: page created")

    return (ipw, browser, ctx, page)


def check_x_login(page: Any, log: Any = None) -> bool:
    """X.comにログイン済みか確認。戻り値: bool"""
    if log:
        log.write("Xにログイン確認中...")
    try:
        page.goto('https://x.com/home', timeout=120000, wait_until='domcontentloaded')
    except Exception as e:
        if log:
            log.write(f"[NG] goto failed: {e}")
        return False
    time.sleep(random.uniform(3, 6))

    if 'login' in page.url.lower():
        if log:
            log.write("[NG] ログイン失敗")
        return False

    if log:
        log.write(f"[OK] ログインOK: {page.url[:50]}")
    return True


def close_browser(ipw: Any, browser: Any, log: Any = None) -> None:
    """invisible_playwright ブラウザを閉じる"""
    try:
        browser.close()
    except Exception as _e:
        if log:
            log.write(f"[WARN] browser.close失敗: {_e}")
    try:
        ipw.__exit__(None, None, None)
    except Exception as _e:
        if log:
            log.write(f"[WARN] ipw.__exit__失敗: {_e}")
    if log:
        log.write("DEBUG: browser closed")
