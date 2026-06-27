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
import math
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
        'locale': 'ja-JP',
        'timezone_id': 'Asia/Tokyo',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0.1',
        'webgl_vendor': 'Google Inc. (Intel)',
        'webgl_renderer': 'Intel HD Graphics 4600 (ANGLE)',
        # ── 行動プロファイル ──
        'profile': {
            'active_hours': ('10:00', '22:00'),
            'max_per_day': {'follow': 35, 'rt': 10, 'like': 60},
            'skip_rate': {'follow': 0.04, 'rt': 0.03, 'like': 0.05},
            'persona': 'anime_manga',
            'work_style': 'steady',
            'typing_speed': 150,
            'click_delay': 80,
            'scroll_pattern': 'smooth',
        },
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
        'locale': 'ja-JP',
        'timezone_id': 'Asia/Tokyo',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0.1',
        'webgl_vendor': 'Google Inc. (Intel)',
        'webgl_renderer': 'Intel Iris Xe Graphics',
        'profile': {
            'active_hours': ('14:00', '02:00'),
            'max_per_day': {'follow': 25, 'rt': 8, 'like': 45},
            'skip_rate': {'follow': 0.02, 'rt': 0.01, 'like': 0.03},
            'persona': 'music_artist',
            'work_style': 'night_owl',
            'typing_speed': 200,
            'click_delay': 120,
            'scroll_pattern': 'erratic',
        },
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
        'locale': 'ja-JP',
        'timezone_id': 'Asia/Tokyo',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; x64; rv:150.0) Gecko/20100101 Firefox/150.0',
        'webgl_vendor': 'Google Inc. (NVIDIA)',
        'webgl_renderer': 'NVIDIA GeForce GTX 1060',
        'profile': {
            'active_hours': ('08:00', '20:00'),
            'max_per_day': {'follow': 40, 'rt': 12, 'like': 70},
            'skip_rate': {'follow': 0.03, 'rt': 0.02, 'like': 0.04},
            'persona': 'gaming_vtuber',
            'work_style': 'morning_person',
            'typing_speed': 100,
            'click_delay': 50,
            'scroll_pattern': 'aggressive',
        },
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
        'locale': 'ja-JP',
        'timezone_id': 'Asia/Tokyo',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0',
        'webgl_vendor': 'Google Inc. (Intel)',
        'webgl_renderer': 'Intel UHD Graphics 620',
        'profile': {
            'active_hours': ('12:00', '23:00'),
            'max_per_day': {'follow': 30, 'rt': 6, 'like': 50},
            'skip_rate': {'follow': 0.03, 'rt': 0.01, 'like': 0.05},
            'persona': 'tech_gadget',
            'work_style': 'burst',
            'typing_speed': 130,
            'click_delay': 60,
            'scroll_pattern': 'measured',
        },
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
        'locale': 'ja-JP',
        'timezone_id': 'Asia/Tokyo',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0',
        'webgl_vendor': 'Google Inc. (AMD)',
        'webgl_renderer': 'AMD Radeon RX 580',
        'profile': {
            'active_hours': ('09:00', '21:00'),
            'max_per_day': {'follow': 20, 'rt': 5, 'like': 35},
            'skip_rate': {'follow': 0.05, 'rt': 0.03, 'like': 0.04},
            'persona': 'life_culture',
            'work_style': 'steady',
            'typing_speed': 220,
            'click_delay': 150,
            'scroll_pattern': 'explorative',
        },
        'tls': {
            'security.tls.version.min': 3,
            'security.tls.version.max': 4,
            'security.tls.hello_downgrade': True,
            'security.ssl.enable_ocsp_stapling': False,
            'security.ssl.enable_ocsp_must_staple': True,
        },
    },
}

# ★ 垢別SOCKS5プロキシ（Windows物理回線個別ルーティング）
PROXY_MAP: dict[str, str] = {
    "atushi16": "socks5h://172.26.80.1:1081",
    "kudou": "socks5h://172.26.80.1:1082",
    "atushi1840": "socks5h://172.26.80.1:1083",
    "zin20120731": "socks5h://172.26.80.1:1084",
    "TankanNotes": "socks5h://172.26.80.1:1085",
}

# ☆ プロキシ有効/無効フラグ（True=有効、False=バイパス）
USE_PROXY: bool = True

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


def human_like_mouse(page: Any, element: Any, click_delay: int = 80) -> None:
    """人間らしいマウス軌跡でクリック（高度ベジェ曲線＋Jitter＋加速減速＋オーバーシュート）
    
    Args:
        page: Playwright page object
        element: クリック対象要素
        click_delay: クリック後の追加待機時間(ms)。ACCOUNT_PROFILES由来で垢別に変動
    """
    box = element.bounding_box()
    if not box:
        vp = page.viewport_size
        cx: int = vp['width'] // 2
        cy: int = vp['height'] // 2
        bx, by = element.evaluate('(el) => {const r = el.getBoundingClientRect(); return [r.x, r.y];}')
        if not bx:
            element.click()
            time.sleep(random.uniform(click_delay * 0.5, click_delay * 1.5) / 1000)
            return
        steps: int = random.randint(10, 20)
        for i in range(steps + 1):
            t: float = i / steps
            u: float = 1 - t
            x: float = u**2 * cx + 2*u*t * (cx + (bx-cx)*0.3) + t**2 * bx
            y: float = u**2 * cy + 2*u*t * (cy + (by-cy)*0.3) + t**2 * cy
            x += random.uniform(-2, 2)
            y += random.uniform(-2, 2)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.01, 0.03))
        page.mouse.click(bx, by)
        time.sleep(random.uniform(click_delay * 0.5, click_delay * 1.5) / 1000)
        return
    vp = page.viewport_size
    start_x: int = random.randint(50, vp['width'] - 50)
    start_y: int = random.randint(50, vp['height'] - 50)
    end_x: float = box['x'] + box['width'] * random.uniform(0.2, 0.8)
    end_y: float = box['y'] + box['height'] * random.uniform(0.2, 0.8)
    overshoot: bool = random.random() < 0.15
    if overshoot:
        overshoot_x: float = end_x + random.uniform(20, 50) * random.choice([-1, 1])
        overshoot_y: float = end_y + random.uniform(20, 50) * random.choice([-1, 1])
    else:
        overshoot_x = end_x
        overshoot_y = end_y
    cx1: float = start_x + (overshoot_x - start_x) * random.uniform(0.1, 0.4)
    cy1: float = start_y + random.uniform(-120, 120)
    cx2: float = overshoot_x + random.uniform(-120, 120)
    cy2: float = overshoot_y + random.uniform(-60, 60)
    steps = random.randint(18, 35)
    t_values: list[float] = []
    for i in range(steps + 1):
        raw: float = i / steps
        eased: float = -(math.cos(math.pi * raw) - 1) / 2
        t_values.append(eased)
    for idx, t in enumerate(t_values):
        u = 1 - t
        x: float = u**3 * start_x + 3*u**2*t * cx1 + 3*u*t**2 * cx2 + t**3 * overshoot_x
        y: float = u**3 * start_y + 3*u**2*t * cy1 + 3*u*t**2 * cy2 + t**3 * overshoot_y
        jitter_mag: float = 0.5 + 2.5 * abs(t - 0.5) * 2
        x += random.uniform(-jitter_mag, jitter_mag)
        y += random.uniform(-jitter_mag, jitter_mag)
        page.mouse.move(x, y)
        speed_factor: float = 1.0 + 0.8 * abs(t - 0.5)
        time.sleep(random.uniform(0.008, 0.030) * speed_factor)
        if idx == steps // 2 and random.random() < 0.10:
            time.sleep(random.uniform(0.05, 0.20))
    if overshoot:
        for i in range(5):
            t = (i + 1) / 6
            x = overshoot_x + (end_x - overshoot_x) * t
            y = overshoot_y + (end_y - overshoot_y) * t
            x += random.uniform(-2, 2)
            y += random.uniform(-2, 2)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.015, 0.04))

    # ── クリック前の「ためらい」動作 ──
    # 1. ターゲットに到達後、50-150ms 滞留
    time.sleep(random.uniform(0.05, 0.15))

    # 2. 15% の確率で「迷い」: 3-8px 揺らす
    if random.random() < 0.15:
        wobble_passes = random.randint(2, 4)
        for _ in range(wobble_passes):
            wobble_x = end_x + random.uniform(-8, 8)
            wobble_y = end_y + random.uniform(-8, 8)
            page.mouse.move(wobble_x, wobble_y)
            time.sleep(random.uniform(0.02, 0.06))

    # 3. 最終ディレイ 30-80ms
    time.sleep(random.uniform(0.03, 0.08))

    page.mouse.click(end_x, end_y)
    time.sleep(random.uniform(click_delay * 0.5, click_delay * 1.5) / 1000)


def create_browser(account_key: str | None = None, session_file: str | None = None,
                   headless: bool = True, log: Any = None,
                   proxy: str | None = None) -> tuple[Any, Any, Any, Any]:
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

    # ★ プロキシ設定
    if USE_PROXY and proxy is None and account_key in PROXY_MAP:
        proxy = PROXY_MAP[account_key]

    # invisible_playwright インスタンス作成（まだ起動しない）
    extra_prefs: dict[str, Any] = {}
    pin: dict[str, Any] = {}
    if fp:
        tls_prefs = fp.get('tls', {})
        extra_prefs.update(tls_prefs)
        if 'webgl_vendor' in fp:
            pin['gpu.vendor'] = fp['webgl_vendor']
        if 'webgl_renderer' in fp:
            pin['gpu.renderer'] = fp['webgl_renderer']
        if 'screen_width' in fp:
            pin['screen.width'] = fp['screen_width']
        if 'screen_height' in fp:
            pin['screen.height'] = fp['screen_height']
        if 'pixel_ratio' in fp:
            pin['screen.dpr'] = fp['pixel_ratio']
    # upstream: proxy/locale/timezone/humanize は InvisiblePlaywright が処理
    proxy_dict = {"server": proxy} if proxy else None
    upstream_locale = fp.get('locale', 'ja-JP') if fp else 'ja-JP'
    upstream_tz = fp.get('timezone_id', '') if fp else ''
    ipw = InvisiblePlaywright(
        seed=seed,
        headless=headless,
        extra_prefs=extra_prefs,
        pin=pin,
        proxy=proxy_dict,
        locale=upstream_locale,
        timezone=upstream_tz,
        humanize=True,
    )

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

    # upstream patched new_context が viewport/screen/DPR/locale/timezone を自動設定
    # → ctx_kwargs には storage_state と user_agent のみ指定
    ctx_kwargs: dict[str, Any] = {
        'storage_state': storage,
    }
    if fp:
        ctx_kwargs['user_agent'] = fp['user_agent']
    ctx = browser.new_context(**ctx_kwargs)

    if log:
        log.write("DEBUG: context created (upstream handles stealth at C++ level)")

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

    # 各種異常状態の検出
    url_lower = page.url.lower()
    if 'login' in url_lower or 'flow' in url_lower or 'signup' in url_lower:
        if log:
            log.write("[NG] needs_login: ログイン画面が検出されました")
        return False

    # ページ本文を取得（不完全な可能性もあるが目安）
    try:
        body_text = page.inner_text('body')
    except Exception:
        body_text = ""
    body_lower = body_text.lower()

    # レート制限
    if 'rate limit' in body_lower or 'rate_limit' in body_lower:
        if log:
            log.write("[NG] rate_limited: レート制限ページが検出されました")
        return False

    # アカウント停止
    if 'account suspended' in body_lower or '凍結' in body_lower or 'suspended' in body_lower:
        if log:
            log.write("[NG] suspended: アカウント停止が検出されました")
        return False

    # reCAPTCHA / Cloudflare チャレンジ
    challenge_elem = page.query_selector('.cf-browser-verification, .challenge, #challenge')
    if challenge_elem or 'challenge' in body_lower:
        if log:
            log.write("[NG] challenge: reCAPTCHA/Cloudflare チャレンジが検出されました")
        return False

    # 他のログイン誘導（i/flow/signup などは URL チェックでカバー済み）

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
