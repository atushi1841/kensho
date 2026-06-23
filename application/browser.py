"""
Kensho Browser — Playwright Firefox ブラウザ制御
v3.4: 垢別指紋偽装 + 型ヒント
"""
from __future__ import annotations

import sys, os, time, random, json
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════
# 垢別ブラウザ指紋（Xが収集する全プロパティを個別化）
# ═══════════════════════════════════════════════════════════
FINGERPRINTS: dict[str, dict[str, Any]] = {
    'atushi16': {
        'hardwareConcurrency': 4,
        'deviceMemory': 4,
        'oscpu': 'Windows NT 10.0; Win64; x64',
        'platform': 'Win32',
        'webgl_vendor': 'Intel Inc.',
        'webgl_renderer': 'Intel(R) HD Graphics 4600',
        'webgl_unmasked_vendor': 'Intel Inc.',
        'webgl_unmasked_renderer': 'Intel(R) HD Graphics 4600',
        'screen_width': 1366,
        'screen_height': 768,
        'color_depth': 24,
        'pixel_ratio': 1.0,
        'plugins': [
            ('OpenH264 Video Codec provided by Cisco Systems, Inc.', 'OpenH264 Video Codec'),
            ('Widevine Content Decryption Module provided by Google Inc.', 'Widevine Content Decryption Module'),
            ('Shockwave Flash', 'Shockwave Flash'),
            ('Adobe Acrobat', 'Adobe Acrobat'),
        ],
        'fonts': ['Arial', 'MS Gothic', 'MS PGothic', 'Meiryo', 'Yu Gothic', 'Times New Roman', 'Courier New'],
        'canvas_noise_seed': 'atushi16_seed_42',
    },
    'kudou': {
        'hardwareConcurrency': 8,
        'deviceMemory': 8,
        'oscpu': 'Windows NT 10.0; Win64; x64',
        'platform': 'Win32',
        'webgl_vendor': 'Google Inc. (NVIDIA)',
        'webgl_renderer': 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)',
        'webgl_unmasked_vendor': 'NVIDIA Corporation',
        'webgl_unmasked_renderer': 'NVIDIA GeForce GTX 1060/PCIe/SSE2',
        'screen_width': 1920,
        'screen_height': 1080,
        'color_depth': 24,
        'pixel_ratio': 1.0,
        'plugins': [
            ('OpenH264 Video Codec provided by Cisco Systems, Inc.', 'OpenH264 Video Codec'),
            ('Widevine Content Decryption Module provided by Google Inc.', 'Widevine Content Decryption Module'),
            ('Shockwave Flash', 'Shockwave Flash'),
            ('Adobe Acrobat', 'Adobe Acrobat'),
            ('Java(TM) Platform SE 8 U251', 'Java(TM) Platform SE 8 U251'),
        ],
        'fonts': ['Arial', 'MS Gothic', 'Meiryo', 'Yu Gothic UI', 'Consolas', 'Segoe UI', 'Verdana', 'Georgia'],
        'canvas_noise_seed': 'kudou_seed_77',
    },
    'atushi1840': {
        'hardwareConcurrency': 6,
        'deviceMemory': 8,
        'oscpu': 'Windows NT 10.0; Win64; x64',
        'platform': 'Win32',
        'webgl_vendor': 'Google Inc. (AMD)',
        'webgl_renderer': 'ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)',
        'webgl_unmasked_vendor': 'AMD',
        'webgl_unmasked_renderer': 'AMD Radeon RX 580',
        'screen_width': 1536,
        'screen_height': 864,
        'color_depth': 24,
        'pixel_ratio': 1.0,
        'plugins': [
            ('OpenH264 Video Codec provided by Cisco Systems, Inc.', 'OpenH264 Video Codec'),
            ('Widevine Content Decryption Module provided by Google Inc.', 'Widevine Content Decryption Module'),
            ('Adobe Acrobat', 'Adobe Acrobat'),
            ('Microsoft Office 2016', 'Microsoft Office 2016'),
        ],
        'fonts': ['Arial', 'MS Gothic', 'MS Mincho', 'Meiryo', 'Yu Gothic', 'Impact', 'Trebuchet MS'],
        'canvas_noise_seed': 'b1840_seed_13',
    },
    'zin20120731': {
        'hardwareConcurrency': 4,
        'deviceMemory': 4,
        'oscpu': 'Windows NT 10.0; Win64; x64',
        'platform': 'Win32',
        'webgl_vendor': 'Google Inc. (Intel)',
        'webgl_renderer': 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)',
        'webgl_unmasked_vendor': 'Intel Inc.',
        'webgl_unmasked_renderer': 'Intel(R) UHD Graphics 620',
        'screen_width': 1366,
        'screen_height': 768,
        'color_depth': 24,
        'pixel_ratio': 1.0,
        'plugins': [
            ('OpenH264 Video Codec provided by Cisco Systems, Inc.', 'OpenH264 Video Codec'),
            ('Widevine Content Decryption Module provided by Google Inc.', 'Widevine Content Decryption Module'),
            ('Shockwave Flash', 'Shockwave Flash'),
        ],
        'fonts': ['Arial', 'MS Gothic', 'MS PGothic', 'Meiryo', 'Yu Gothic', 'Segoe UI', 'Consolas'],
        'canvas_noise_seed': 'zin20120731_seed_55',
    },
}


def build_stealth_script(fp: dict[str, Any]) -> str:
    """垢ごとに異なるブラウザ指紋を生成するJS"""
    plugins_js: str = ', '.join(
        f'{{ name: "{n}", filename: "{f}.dll", description: "{n}" }}'
        for n, f in fp['plugins']
    )
    fonts_js: str = json.dumps(fp['fonts'])
    seed_val: int = sum(ord(c) for c in fp['canvas_noise_seed'])

    return f"""
// ══════════════ Kensho Stealth v3.3 — 垢別指紋 ══════════════

// 1. webdriver 無効化
Object.defineProperty(navigator, 'webdriver', {{
    get: () => undefined,
    configurable: true,
}});
delete Object.getPrototypeOf(navigator).webdriver;

// 2. plugins（垢別）
Object.defineProperty(navigator, 'plugins', {{
    get: () => {{
        const arr = [{plugins_js}];
        arr.item = i => arr[i] || null;
        arr.namedItem = n => arr.find(p => p.name === n) || null;
        arr.refresh = () => {{}};
        return arr;
    }},
    configurable: true,
}});

// 3. mimeTypes
Object.defineProperty(navigator, 'mimeTypes', {{
    get: () => {{
        const arr = [
            {{ type: 'application/x-shockwave-flash', suffixes: 'swf', description: 'Shockwave Flash' }},
            {{ type: 'video/mp4', suffixes: 'mp4', description: 'MP4 Video' }},
            {{ type: 'audio/mpeg', suffixes: 'mp3', description: 'MPEG Audio' }},
        ];
        arr.item = i => arr[i] || null;
        arr.namedItem = n => arr.find(m => m.type === n) || null;
        return arr;
    }},
    configurable: true,
}});

// 4. languages
Object.defineProperty(navigator, 'languages', {{
    get: () => ['ja-JP', 'ja', 'en-US', 'en'],
    configurable: true,
}});
Object.defineProperty(navigator, 'language', {{
    get: () => 'ja-JP',
    configurable: true,
}});

// 5. oscpu（垢別）
Object.defineProperty(navigator, 'oscpu', {{
    get: () => '{fp["oscpu"]}',
    configurable: true,
}});

// 6. hardwareConcurrency（垢別）
Object.defineProperty(navigator, 'hardwareConcurrency', {{
    get: () => {fp['hardwareConcurrency']},
    configurable: true,
}});

// 7. deviceMemory（垢別）
Object.defineProperty(navigator, 'deviceMemory', {{
    get: () => {fp['deviceMemory']},
    configurable: true,
}});

// 8. platform（垢別）
Object.defineProperty(navigator, 'platform', {{
    get: () => '{fp['platform']}',
    configurable: true,
}});

// 9. Canvas フィンガープリント（垢別ノイズ）
(function() {{
    const seed = {seed_val};
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    const origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function() {{
        const ctx = origGetContext.apply(this, arguments);
        if (arguments[0] === '2d' && ctx) {{
            const origFillText = ctx.fillText;
            ctx.fillText = function() {{
                ctx.shadowBlur = 0.5 + (seed % 3) * 0.1;
                ctx.shadowColor = 'rgba(0,0,0,0.01)';
                origFillText.apply(this, arguments);
                ctx.shadowBlur = 0;
            }};
        }}
        return ctx;
    }};
}})();

// 10. WebGL フィンガープリント（垢別GPU偽装）
(function() {{
    const origGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {{
        const ext = this.getExtension('WEBGL_debug_renderer_info');
        if (ext) {{
            if (p === ext.UNMASKED_VENDOR_WEBGL) return '{fp["webgl_unmasked_vendor"]}';
            if (p === ext.UNMASKED_RENDERER_WEBGL) return '{fp["webgl_unmasked_renderer"]}';
        }}
        if (p === 0x1F00) return '{fp["webgl_vendor"]}';
        if (p === 0x1F01) return '{fp["webgl_renderer"]}';
        try {{ return origGetParameter.call(this, p); }} catch(e) {{ return null; }}
    }};
    if (typeof WebGL2RenderingContext !== 'undefined') {{
        WebGL2RenderingContext.prototype.getParameter = WebGLRenderingContext.prototype.getParameter;
    }}
}})();

// 11. Screen 情報（垢別解像度）
Object.defineProperty(screen, 'width', {{ get: () => {fp['screen_width']}, configurable: true }});
Object.defineProperty(screen, 'height', {{ get: () => {fp['screen_height']}, configurable: true }});
Object.defineProperty(screen, 'availWidth', {{ get: () => {fp['screen_width']}, configurable: true }});
Object.defineProperty(screen, 'availHeight', {{ get: () => {fp['screen_height'] - 40}, configurable: true }});
Object.defineProperty(screen, 'colorDepth', {{ get: () => {fp['color_depth']}, configurable: true }});
Object.defineProperty(screen, 'pixelDepth', {{ get: () => {fp['color_depth']}, configurable: true }});

// 12. Touch support
Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => 0, configurable: true }});

// 13. Notification API
if (typeof Notification !== 'undefined') {{
    const origPermission = Object.getOwnPropertyDescriptor(Notification, 'permission');
    if (!origPermission) {{
        Object.defineProperty(Notification, 'permission', {{
            get: () => 'default',
            configurable: true,
        }});
    }}
}}

// 14. navigator.connection 偽装
try {{
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conn) {{
        Object.defineProperty(conn, 'effectiveType', {{ get: () => '4g', configurable: true }});
        Object.defineProperty(conn, 'rtt', {{ get: () => 50, configurable: true }});
        Object.defineProperty(conn, 'downlink', {{ get: () => 10, configurable: true }});
        Object.defineProperty(conn, 'saveData', {{ get: () => false, configurable: true }});
    }}
}} catch(e) {{}}

// 15. Fonts 列挙偽装
if (typeof window.queryLocalFonts !== 'undefined') {{
    window.queryLocalFonts = () => Promise.resolve(
        {fonts_js}.map(name => ({{ family: name, fullName: name, postscriptName: name.replace(/ /g, '') }}))
    );
}}

// 16. doNotTrack
Object.defineProperty(navigator, 'doNotTrack', {{ get: () => '1', configurable: true }});
"""


def random_viewport(page: Any) -> None:
    """ランダムなビューポート（fingerprintが無い場合のフォールバック）"""
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
    標準 Playwright Firefox ブラウザを起動。
    account_key が指定されていれば、垢別指紋を適用。

    session_file: セッションJSONのパス（auth_token/cookie注入用）
    戻り値: (playwright, browser, context, page)
    """
    from playwright.sync_api import sync_playwright

    if log:
        log.write(f"DEBUG: Playwright Firefox starting (account={account_key})")

    pw = sync_playwright().start()
    browser = pw.firefox.launch(
        headless=headless,
        firefox_user_prefs={
            "dom.webdriver.enabled": False,
            "useAutomationExtension": False,
        }
    )

    if log:
        log.write("DEBUG: Firefox browser launched")

    storage = None
    if session_file and os.path.exists(session_file):
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                storage = json.load(f)
        except Exception as e:
            if log:
                log.write(f"WARN: session file read error: {e}")
    # keyring優先（ファイルより新しいデータがあれば上書き）
    if account_key:
        from utils.keyring import load_session as _kr_load
        kr_data = _kr_load(account_key)
        if kr_data:
            storage = kr_data
            if log:
                log.write(f"  [KEYRING] Session loaded from Credential Manager")

    fp: dict[str, Any] | None = FINGERPRINTS.get(account_key) if account_key else None
    if fp and log:
        log.write(f"  [FINGERPRINT] {account_key}: {fp['webgl_unmasked_renderer'][:40]}...")

    device_scale: float = fp['pixel_ratio'] if fp else random.choice([1.0, 1.25, 1.5])
    ctx = browser.new_context(
        storage_state=storage,
        locale='ja-JP',
        timezone_id='Asia/Tokyo',
        device_scale_factor=device_scale,
    )

    if fp:
        stealth_js = build_stealth_script(fp)
    else:
        stealth_js = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
delete Object.getPrototypeOf(navigator).webdriver;
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const arr = [
            { name: 'OpenH264 Video Codec', filename: 'openh264plugin.dll' },
            { name: 'Widevine Content Decryption Module', filename: 'widevinecdm.dll' },
            { name: 'GStreamer WebRTC Plugin', filename: 'gstwebrtc.dll' },
        ];
        arr.item = i => arr[i] || null;
        arr.namedItem = n => arr.find(p => p.name === n) || null;
        arr.refresh = () => {};
        return arr;
    }
});
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => {
        const arr = [
            { type: 'video/mp4', suffixes: 'mp4' },
            { type: 'audio/mpeg', suffixes: 'mp3' },
            { type: 'video/webm', suffixes: 'webm' },
        ];
        arr.item = i => arr[i] || null;
        arr.namedItem = n => arr.find(t => t.type === n) || null;
        return arr;
    }
});
"""
    ctx.add_init_script(stealth_js)

    if log:
        log.write("DEBUG: context created")

    page = ctx.new_page()

    if fp:
        set_viewport_for_fingerprint(page, fp)
    else:
        random_viewport(page)

    if log:
        log.write("DEBUG: page created")

    return (pw, browser, ctx, page)


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


def close_browser(pw: Any, browser: Any, log: Any = None) -> None:
    """ブラウザを閉じる"""
    try:
        browser.close()
    except Exception as _e:
        if log:
            log.write(f"[WARN] browser.close失敗: {_e}")
    try:
        pw.stop()
    except Exception as _e:
        if log:
            log.write(f"[WARN] pw.stop失敗: {_e}")
    if log:
        log.write("DEBUG: browser closed")
