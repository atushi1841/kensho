#!/usr/bin/env python3
"""
Kensho Browser — invisible_playwright Firefox ブラウザ制御
v4.0: C++レベル指紋偽装（invisible_playwright）+ アカウント別シード
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
from typing import Any

import psutil

# ── anti-detect browser selector ──
# patchright が利用可能なら優先使用（C++レベル指紋偽装・CDP漏洩対策）
# フォールバック: 標準の playwright
_PATCHRIGHT_AVAILABLE: bool = False
try:
    from patchright.sync_api import sync_playwright as _patchright_sync_playwright

    _PATCHRIGHT_AVAILABLE = True
except ImportError:
    pass
if not _PATCHRIGHT_AVAILABLE:
    try:
        from playwright.sync_api import sync_playwright as _patchright_sync_playwright  # noqa: F811
    except ImportError:
        _patchright_sync_playwright = None  # type: ignore[assignment]

# ── check_x_login constants ──
_CHECK_LOGIN_TIMEOUT: int = 30000
_CHECK_LOGIN_MAX_ATTEMPTS: int = 3
_CHECK_LOGIN_RETRY_DELAY: int = 5
_CHECK_LOGIN_FUTURE_TIMEOUT: int = 35

# ═══════════════════════════════════════════════════════════
# 垢別ブラウザ指紋コンセプト（固定シード値）
# invisible_playwright はC++レベルで偽装するため、
# ここでは reproduce 用のシードと画面解像度のみ管理。
# ═══════════════════════════════════════════════════════════
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
        # ── 行動プロファイル ──
        "profile": {
            "active_hours": ("10:00", "22:00"),
            "max_per_day": {"follow": 35, "rt": 10, "like": 60},
            "skip_rate": {"follow": 0.04, "rt": 0.03, "like": 0.05},
            "persona": "anime_manga",
            "work_style": "steady",
            "typing_speed": 150,
            "click_delay": 80,
            "scroll_pattern": "smooth",
        },
        "tls": {
            "security.tls.version.min": 3,
            "security.tls.version.max": 4,
            "security.tls.hello_downgrade": False,
            "security.ssl.enable_ocsp_stapling": True,
            "security.ssl.enable_ocsp_must_staple": False,
        },
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
        "profile": {
            "active_hours": ("14:00", "02:00"),
            "max_per_day": {"follow": 25, "rt": 8, "like": 45},
            "skip_rate": {"follow": 0.02, "rt": 0.01, "like": 0.03},
            "persona": "music_artist",
            "work_style": "night_owl",
            "typing_speed": 200,
            "click_delay": 120,
            "scroll_pattern": "erratic",
        },
        "tls": {
            "security.tls.version.min": 3,
            "security.tls.version.max": 4,
            "security.tls.hello_downgrade": True,
            "security.ssl.enable_ocsp_stapling": True,
            "security.ssl.enable_ocsp_must_staple": True,
        },
    },
    "atushi1840": {
        "seed": 13,
        "accept_language": "ja-JP,ja;q=0.8,en-US;q=0.7",
        "screen_width": 1536,
        "screen_height": 864,
        "pixel_ratio": 1.0,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "NVIDIA GeForce GTX 1060",
        "profile": {
            "active_hours": ("08:00", "20:00"),
            "max_per_day": {"follow": 40, "rt": 12, "like": 70},
            "skip_rate": {"follow": 0.03, "rt": 0.02, "like": 0.04},
            "persona": "gaming_vtuber",
            "work_style": "morning_person",
            "typing_speed": 100,
            "click_delay": 50,
            "scroll_pattern": "aggressive",
        },
        "tls": {
            "security.tls.version.min": 3,
            "security.tls.version.max": 4,
            "security.tls.hello_downgrade": True,
            "security.ssl.enable_ocsp_stapling": False,
            "security.ssl.enable_ocsp_must_staple": False,
        },
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
        "profile": {
            "active_hours": ("12:00", "23:00"),
            "max_per_day": {"follow": 30, "rt": 6, "like": 50},
            "skip_rate": {"follow": 0.03, "rt": 0.01, "like": 0.05},
            "persona": "tech_gadget",
            "work_style": "burst",
            "typing_speed": 130,
            "click_delay": 60,
            "scroll_pattern": "measured",
        },
        "tls": {
            "security.tls.version.min": 3,
            "security.tls.version.max": 4,
            "security.tls.hello_downgrade": False,
            "security.ssl.enable_ocsp_stapling": True,
            "security.ssl.enable_ocsp_must_staple": True,
        },
    },
    "TankanNotes": {
        "seed": 91,
        "accept_language": "ja-JP,ja;q=0.9,en;q=0.8,ko;q=0.5",
        "screen_width": 1440,
        "screen_height": 900,
        "pixel_ratio": 1.0,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
        "webgl_vendor": "Google Inc. (AMD)",
        "webgl_renderer": "AMD Radeon RX 580",
        "profile": {
            "active_hours": ("09:00", "21:00"),
            "max_per_day": {"follow": 20, "rt": 5, "like": 35},
            "skip_rate": {"follow": 0.05, "rt": 0.03, "like": 0.04},
            "persona": "life_culture",
            "work_style": "steady",
            "typing_speed": 220,
            "click_delay": 150,
            "scroll_pattern": "explorative",
        },
        "tls": {
            "security.tls.version.min": 3,
            "security.tls.version.max": 4,
            "security.tls.hello_downgrade": True,
            "security.ssl.enable_ocsp_stapling": False,
            "security.ssl.enable_ocsp_must_staple": True,
        },
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
        "profile": {
            "active_hours": ("09:00", "21:00"),
            "max_per_day": {"follow": 40, "rt": 12, "like": 70},
            "skip_rate": {"follow": 0.03, "rt": 0.02, "like": 0.04},
            "persona": "book_culture",
            "work_style": "morning_person",
            "typing_speed": 100,
            "click_delay": 50,
            "scroll_pattern": "aggressive",
        },
        "tls": {
            "security.tls.version.min": 3,
            "security.tls.version.max": 4,
            "security.tls.hello_downgrade": True,
            "security.ssl.enable_ocsp_stapling": True,
            "security.ssl.enable_ocsp_must_staple": False,
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
    "inobase1-4": "socks5h://172.26.80.1:1089",
}

# ☆ プロキシ有効/無効フラグ（True=有効、False=バイパス）
USE_PROXY: bool = os.environ.get("USE_PROXY", "True").lower() == "true"

# invisible_playwright は使わないが、型の互換性のためにエイリアス
# build_stealth_script は C++レベル偽装に置き換えたため削除


def random_viewport(page: Any) -> None:
    """ランダムなビューポート"""
    w: int = random.choice([1366, 1440, 1536, 1600, 1680, 1720, 1920])
    h: int = random.choice([768, 800, 864, 900, 960, 1024, 1080])
    page.set_viewport_size({"width": w, "height": h})


def set_viewport_for_fingerprint(page: Any, fp: dict[str, Any]) -> None:
    """指紋と一致するビューポートを設定"""
    page.set_viewport_size({"width": fp["screen_width"], "height": fp["screen_height"]})


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
        cx: int = vp["width"] // 2
        cy: int = vp["height"] // 2
        bx, by = element.evaluate("(el) => {const r = el.getBoundingClientRect(); return [r.x, r.y];}")
        if not bx:
            element.click()
            time.sleep(random.uniform(click_delay * 0.5, click_delay * 1.5) / 1000)
            return
        steps: int = random.randint(10, 20)
        for i in range(steps + 1):
            t: float = i / steps
            u: float = 1 - t
            x: float = u**2 * cx + 2 * u * t * (cx + (bx - cx) * 0.3) + t**2 * bx
            y: float = u**2 * cy + 2 * u * t * (cy + (by - cy) * 0.3) + t**2 * cy
            x += random.uniform(-2, 2)
            y += random.uniform(-2, 2)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.01, 0.03))
        page.mouse.click(bx, by)
        time.sleep(random.uniform(click_delay * 0.5, click_delay * 1.5) / 1000)
        return
    vp = page.viewport_size
    start_x: int = random.randint(50, vp["width"] - 50)
    start_y: int = random.randint(50, vp["height"] - 50)
    end_x: float = box["x"] + box["width"] * random.uniform(0.2, 0.8)
    end_y: float = box["y"] + box["height"] * random.uniform(0.2, 0.8)
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
        x: float = u**3 * start_x + 3 * u**2 * t * cx1 + 3 * u * t**2 * cx2 + t**3 * overshoot_x
        y: float = u**3 * start_y + 3 * u**2 * t * cy1 + 3 * u * t**2 * cy2 + t**3 * overshoot_y
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


def _build_stealth_js(fp: dict[str, Any] | None) -> str:
    """アカウント別JSレベルの完全偽装コードを生成。

    Service Worker / AudioBuffer / Performance / Canvas / Navigator / MediaDevices /
    Permissions / WebGL拡張 / WebRTC / Plugins / platform / Canvas getImageData / toBlob
    を垢別seedに基づいて偽装。
    このJSは C++レベル偽装（invisible_playwright）を補完する第2層。
    JSは実改行(ASCII 10)で行を結合 — コメントが後続コードを食わない。
    """
    seed = fp["seed"] if fp else 42
    canvas_noise = (seed * 13 + 7) % 1000 / 10000.0
    hc_cores = [4, 8, 6, 12, 16][seed % 5]
    wgl_variant = seed % 4
    lines = [
        "// ── Kensho JavaScript Stealth Layer v2（全面カバー）──",
        "(async()=>{",
        "try{",
        f"let _seed={seed}; let _cn={canvas_noise};",
        "// 1. Service Worker unregister（XのSW追跡防止）",
        "if(navigator.serviceWorker){",
        "  try{",
        "    const regs=await navigator.serviceWorker.getRegistrations();",
        "    for(const r of regs){await r.unregister();}",
        "  }catch(e){}",
        "}",
        "// 1.5 navigator.webdriver を undefined に上書き（自動化検出回避）",
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});",
        "// 2. AudioBuffer.getChannelData にseed別ノイズ注入",
        "let _origGCD=AudioBuffer.prototype.getChannelData;",
        "AudioBuffer.prototype.getChannelData=function(c){",
        "  let a=_origGCD.apply(this,arguments);",
        "  for(let i=0;i<a.length;i++){a[i]+=(Math.random()-0.5)*_cn*0.1;}",
        "  return a;",
        "};",
        "// 3. Performance.now() にseed別オフセット",
        "let _origPN=performance.now.bind(performance);",
        "performance.now=()=>_origPN()+(_seed%47)*0.013;",
        "// 4. Canvas.toDataURL 微量改変（seed別）",
        "let _origTDU=HTMLCanvasElement.prototype.toDataURL;",
        "HTMLCanvasElement.prototype.toDataURL=function(...a){",
        "  let b=_origTDU.apply(this,a);",
        "  if(b.length<50)return b;",
        "  let i=b.length-4,c=b.charAt(i);",
        '  let cs="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";',
        "  let nc=cs.charAt((cs.indexOf(c)+Math.floor(_cn*10))%cs.length);",
        "  return b.substring(0,i)+nc+b.substring(i+1);",
        "};",
        f"// 5. Navigator.hardwareConcurrency 固定（{hc_cores}コア）",
        f'Object.defineProperty(navigator,"hardwareConcurrency",{{get:()=>{hc_cores}}});',
        "// 6. navigator.connection を削除（Firefox未実装を維持）",
        'Object.defineProperty(navigator,"connection",{get:()=>undefined});',
        "// 7. MediaDevices 固定ダミーリスト（カメラ1台＋マイク1台）",
        "if(navigator.mediaDevices&&navigator.mediaDevices.enumerateDevices){",
        "  let _origED=navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);",
        "  navigator.mediaDevices.enumerateDevices=async()=>{",
        "    return[",
        '      {deviceId:"default",kind:"audioinput",label:"",groupId:"default"},',
        '      {deviceId:"default",kind:"audiooutput",label:"",groupId:"default"},',
        "    ];",
        "  };",
        "}",
        "// 8. Permissions API 固定（geolocation/notifications を denied）",
        "if(navigator.permissions&&navigator.permissions.query){",
        "  let _origPQ=navigator.permissions.query.bind(navigator.permissions);",
        "  navigator.permissions.query=(desc)=>{",
        '    if(desc&&(desc.name==="geolocation"||desc.name==="notifications"))',
        '      return Promise.resolve({state:"denied",onchange:null});',
        "    return _origPQ(desc);",
        "  };",
        "}",
        f"// 9. WebGL getExtension 制限（variant {wgl_variant}）",
        f"let _wglVariant={wgl_variant};",
        "let _allowedExts=[",
        '  "EXT_blend_minmax","EXT_color_buffer_half_float","EXT_disjoint_timer_query",',
        '  "EXT_float_blend","EXT_frag_depth","EXT_shader_texture_lod",',
        '  "EXT_texture_compression_rgtc","EXT_texture_filter_anisotropic",',
        '  "OES_element_index_uint","OES_fbo_render_mipmap","OES_standard_derivatives",',
        '  "OES_texture_float","OES_texture_half_float","OES_texture_half_float_linear",',
        '  "OES_vertex_array_object","WEBGL_color_buffer_float","WEBGL_compressed_texture_s3tc",',
        '  "WEBGL_compressed_texture_s3tc_srgb","WEBGL_debug_renderer_info",',
        '  "WEBGL_lose_context","MOZ_WEBGL_lose_context",',
        "];",
        "let _origGE=WebGLRenderingContext.prototype.getExtension;",
        "WebGLRenderingContext.prototype.getExtension=function(e){",
        "  if(!_allowedExts.includes(e))return null;",
        "  let ext=_origGE.apply(this,arguments);",
        "  return ext;",
        "};",
        "// 10. WebRTC：RTCPeerConnection を握殺（Firefox pref の二重ロック）",
        "if(window.RTCPeerConnection){",
        "  window.RTCPeerConnection=function(){return{close:()=>{}}};",
        "  window.RTCPeerConnection.prototype={close:()=>{}};",
        "  window.webkitRTCPeerConnection=undefined;",
        "}",
        "// 11. navigator.plugins 偽装（Firefox標準の3プラグイン）",
        "let _plugins=[",
        '  {name:"Widevine Content Decryption Module",filename:"widevinecdm.dll",description:"Enables Widevine encrypted media playback",version:"4.10.2830.0"},',
        '  {name:"OpenH264 Video Codec",filename:"openh264.dll",description:"OpenH264 video codec by Cisco",version:"2.4.1"},',
        '  {name:"Google Talk Plugin Video Accelerator",filename:"npGoogleTalkPlugin.dll",description:"Google Talk Plugin Video Accelerator",version:"5.4.0"},',
        "];",
        "Object.defineProperty(navigator,'plugins',{get:()=>{",
        "  let p=[];",
        "  for(let x of _plugins){",
        "    let pi={name:x.name,filename:x.filename,description:x.description,version:x.version,length:0,item:()=>null,namedItem:()=>null};",
        "    pi.__proto__=Plugin.prototype;",
        "    p.push(pi);",
        "  }",
        "  p.item=(i)=>i>=0&&i<p.length?p[i]:null;",
        "  p.namedItem=(n)=>p.find(x=>x.name===n)||null;",
        "  p.refresh=()=>{};",
        "  p.__proto__=PluginArray.prototype;",
        "  return p;",
        "}});",
        "// 12. navigator.oscpu / platform 整合性（UAと一致）",
        'Object.defineProperty(navigator,"oscpu",{get:()=>"Windows NT 10.0; Win64; x64"});',
        'Object.defineProperty(navigator,"platform",{get:()=>"Win64"});',
        'Object.defineProperty(navigator,"pdfViewerEnabled",{get:()=>true});',
        "// 13. Canvas getImageData 微量ノイズ（seed別）",
        "let _origGID=CanvasRenderingContext2D.prototype.getImageData;",
        "CanvasRenderingContext2D.prototype.getImageData=function(...a){",
        "  let imgData=_origGID.apply(this,a);",
        "  let d=imgData.data;",
        "  for(let i=0;i<d.length;i+=4){",
        "    d[i]+=Math.floor((Math.sin(i*_seed)*_cn*255+_cn*128)%3-1);",
        "    d[i+1]+=Math.floor((Math.cos(i*_seed)*_cn*255+_cn*128)%3-1);",
        "    d[i+2]+=Math.floor((Math.sin(i*_seed*2)*_cn*255+_cn*128)%3-1);",
        "  }",
        "  return imgData;",
        "};",
        "// 14. Canvas toBlob ノイズ（toDataURLと同じロジック）",
        "let _origTB=HTMLCanvasElement.prototype.toBlob;",
        "HTMLCanvasElement.prototype.toBlob=function(cb,...a){",
        "  let _this=this;",
        "  _origTB.call(_this,function(b){",
        "    if(!b||b.size<50){cb(b);return;}",
        "    let reader=new FileReader();",
        "    reader.onloadend=function(){",
        "      let data=reader.result;",
        "      let i=data.length-4,c=data.charAt(i);",
        '      let cs="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";',
        "      let nc=cs.charAt((cs.indexOf(c)+Math.floor(_cn*10))%cs.length);",
        "      let modified=data.substring(0,i)+nc+data.substring(i+1);",
        "      fetch(modified).then(r=>r.blob()).then(cb).catch(()=>cb(b));",
        "    };",
        "    reader.readAsDataURL(b);",
        "  },...a);",
        "};",
        "}catch(e){})()",
    ]
    return "\n".join(lines)


def create_browser(
    account_key: str | None = None,
    session_file: str | None = None,
    headless: bool = True,
    log: Any = None,
    proxy: str | None = None,
) -> tuple[Any, Any, Any, Any]:
    """
    invisible_playwright Firefox ブラウザを起動（C++レベル指紋偽装）。
    account_key が指定されていれば、垢別固定シードで指紋を再現。

    戻り値: (invisible_pw_instance, browser, context, page)
    invisible_pw_instance は close_browser() で終了処理に使う。
    """

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

    # ★ プロキシ設定
    if USE_PROXY and proxy is None and account_key in PROXY_MAP:
        proxy = PROXY_MAP[account_key]

    # invisible_playwright インスタンス作成（まだ起動しない）
    extra_prefs: dict[str, Any] = {}

    # ── Firefoxメモリ制限（cgroup OOM対策）──
    # コンテンツプロセスを1つに制限 → RSS 2-3GB → 500-800MBに削減
    extra_prefs["dom.ipc.processCount"] = 1
    extra_prefs["dom.ipc.processCount.max"] = 1
    extra_prefs["dom.ipc.processPrelaunch.enabled"] = False
    extra_prefs["dom.ipc.keepProcessesAlive.web"] = 0
    extra_prefs["javascript.options.mem.max"] = 256000  # 256MB JS heap
    extra_prefs["browser.tabs.unloadOnLowMemory"] = True  # 低メモリ時タブ解放
    extra_prefs["browser.sessionhistory.max_entries"] = 10  # セッション履歴削減（メモリ節約）
    extra_prefs["browser.sessionhistory.max_total_viewers"] = 0  # bfcache完全無効（数百MB節約）
    extra_prefs["browser.cache.memory.enable"] = False  # メモリキャッシュ無効
    extra_prefs["media.peerconnection.enabled"] = True  # WebRTC有効（無効化はfingerprint異常と判定されるリスク）
    extra_prefs["media.peerconnection.ice.obfuscate_host_addresses"] = True  # 内部IP漏洩防止
    extra_prefs["media.memory_cache_max_size"] = 2048  # メディアキャッシュ最小

    # ── Firefox軽量化prefs（BOT対策に影響しないもののみ）──
    extra_prefs["browser.sessionstore.resume_from_crash"] = False
    extra_prefs["browser.startup.homepage"] = "about:blank"
    extra_prefs["datareporting.policy.dataSubmissionEnabled"] = False
    extra_prefs["media.autoplay.enabled"] = False
    extra_prefs["toolkit.telemetry.reportingpolicy.firstRun"] = False

    pin: dict[str, Any] = {}
    if fp:
        tls_prefs = fp.get("tls", {})
        extra_prefs.update(tls_prefs)
        if "webgl_vendor" in fp:
            pin["gpu.vendor"] = fp["webgl_vendor"]
        if "webgl_renderer" in fp:
            pin["gpu.renderer"] = fp["webgl_renderer"]
        if "screen_width" in fp:
            pin["screen.width"] = fp["screen_width"]
        if "screen_height" in fp:
            pin["screen.height"] = fp["screen_height"]
        if "pixel_ratio" in fp:
            pin["screen.dpr"] = fp["pixel_ratio"]
    # upstream: proxy/locale/timezone/humanize は標準Playwrightで処理
    proxy_dict = {"server": proxy} if proxy else None

    # SOCKS5プロキシはFirefox prefs経由で設定（Playwright proxyは標準Firefoxと競合）
    if proxy_dict:
        # socks5:// または socks5h:// の両方に対応
        proxy_str = proxy_dict["server"].replace("socks5h://", "").replace("socks5://", "")
        proxy_host, proxy_port_str = proxy_str.split(":")
        proxy_port = int(proxy_port_str)
        extra_prefs["network.proxy.type"] = 1
        extra_prefs["network.proxy.socks"] = proxy_host
        extra_prefs["network.proxy.socks_port"] = proxy_port
        extra_prefs["network.proxy.socks_version"] = 5
        extra_prefs["network.proxy.socks_remote_dns"] = True

    # UA と Accept-Language を prefs で設定（extra_http_headersはプロキシ競合のためNG）
    if fp:
        extra_prefs["general.useragent.override"] = fp["user_agent"]
        accept_lang = fp.get("accept_language", "ja-JP,ja;q=0.9,en-US;q=0.8")
        extra_prefs["intl.accept_languages"] = accept_lang

    # ★ Playwright Sync API でブラウザ起動（標準Playwright Firefox）
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.set_event_loop(None)
    except RuntimeError:
        pass
    pw = _patchright_sync_playwright().start()
    engine = "patchright" if _PATCHRIGHT_AVAILABLE else "playwright (std)"
    if log:
        log.write(f"  Browser engine: {engine}")
    browser = pw.firefox.launch(
        headless=headless,
        firefox_user_prefs=extra_prefs,
    )

    if log:
        log.write("DEBUG: Firefox browser launched (invisible_playwright)")

    # ── セッション読み込み（auth_token等）──
    storage = None
    if session_file and os.path.exists(session_file):
        try:
            with open(session_file, encoding="utf-8") as f:
                storage = json.load(f)
        except Exception as e:
            if log:
                log.write(f"WARN: session file read error: {e}")
    # keyring優先
    if account_key:
        from kensho.utils.keyring import load_session as _kr_load

        kr_data = _kr_load(account_key)
        if kr_data:
            storage = kr_data
            if log:
                log.write("  [KEYRING] Session loaded from Credential Manager")

    if fp and log:
        log.write(f"  [FINGERPRINT] {account_key}: seed={fp['seed']}")

    # ★ コンテキスト作成（InvisiblePlaywrightから取得）
    ctx_kwargs: dict[str, Any] = {
        "storage_state": storage,
    }

    # ★ Browser/BrowserContext 両対応
    ctx: Any = browser
    if hasattr(ctx, "pages"):
        # BrowserContext の場合（profile_dir有り → persistent context）
        if log:
            log.write("DEBUG: using InvisiblePlaywright BrowserContext directly")
        pages = ctx.pages
    elif hasattr(ctx, "contexts"):
        # Browser の場合（profile_dir無し → new_context で作成）
        if log:
            log.write("DEBUG: using InvisiblePlaywright Browser, creating context")
        contexts = ctx.contexts
        if contexts:
            ctx = contexts[0]
        else:
            ctx = browser.new_context(**ctx_kwargs)
        pages = ctx.pages
    else:
        if log:
            log.write("DEBUG: unknown browser type, creating new context")
        ctx = browser.new_context(**ctx_kwargs)
        pages = ctx.pages
    if pages:
        page = pages[0]
        if log:
            log.write("DEBUG: using existing page from persistent context")
    else:
        page = ctx.new_page()
        if log:
            log.write("DEBUG: created new page")

    if fp:
        set_viewport_for_fingerprint(page, fp)
    else:
        random_viewport(page)

    page.set_default_timeout(60000)  # ページ操作の最大待機時間

    # ★ JavaScript Stealth Layer 注入（C++レベル偽装の補完）
    #   Service Worker unregister / AudioBuffer ノイズ / Performance オフセット / Canvas 改変
    js_code = _build_stealth_js(fp)
    page.add_init_script(js_code)

    if log:
        log.write("DEBUG: page created")

    return (pw, browser, ctx, page)


def check_x_login(page: Any, log: Any = None, screen_name: str | None = None) -> bool:
    """X.comにログイン済みか確認。戻り値: bool"""
    if log:
        log.write("Xにログイン確認中...")

    page.set_default_timeout(_CHECK_LOGIN_TIMEOUT)

    max_attempts = _CHECK_LOGIN_MAX_ATTEMPTS
    for attempt in range(1, max_attempts + 1):
        try:
            page.goto("https://x.com/home", timeout=_CHECK_LOGIN_TIMEOUT, wait_until="commit")
            break
        except Exception as e:
            if log:
                log.write(f"[NG] goto failed (attempt {attempt}): {e}")
            if attempt < max_attempts:
                time.sleep(_CHECK_LOGIN_RETRY_DELAY)
            else:
                return False
    time.sleep(random.uniform(3, 6))

    # 各種異常状態の検出
    url_lower = page.url.lower()
    if "login" in url_lower or "flow" in url_lower or "signup" in url_lower:
        if log:
            log.write("[NG] needs_login: ログイン画面が検出されました")
        return False

    # ページ本文を取得（不完全な可能性もあるが目安）
    try:
        body_text = page.inner_text("body")
    except Exception:
        body_text = ""
    body_lower = body_text.lower()

    # レート制限
    if "rate limit" in body_lower or "rate_limit" in body_lower:
        if log:
            log.write("[NG] rate_limited: レート制限ページが検出されました")
        return False

    # アカウント停止
    if "account suspended" in body_lower or "凍結" in body_lower or "suspended" in body_lower:
        if log:
            log.write("[NG] suspended: アカウント停止が検出されました")
        return False

    # reCAPTCHA / Cloudflare チャレンジ
    challenge_elem = page.query_selector(".cf-browser-verification, .challenge, #challenge")
    if challenge_elem or "challenge" in body_lower:
        if log:
            log.write("[NG] challenge: reCAPTCHA/Cloudflare チャレンジが検出されました")
        return False

    # 他のログイン誘導（i/flow/signup などは URL チェックでカバー済み）

    if screen_name:
        try:
            page.goto(f"https://x.com/{screen_name}", timeout=15000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))
            profile_body = page.inner_text("body")
            profile_lower = profile_body.lower()
            frozen_keywords = (
                "凍結",
                "読み取り専用",
                "suspended",
                "read-only",
                "read only",
                "restricted",
                "制限されています",
            )
            if any(kw in profile_lower for kw in frozen_keywords):
                if log:
                    log.write("[NG] frozen: アカウント凍結（読み取り専用）が検出されました")
                return False
        except Exception:
            if log:
                log.write("[WARN] プロフィール確認失敗（続行）")
            pass

    if log:
        log.write(f"[OK] ログインOK: {page.url[:50]}")
    return True


def close_browser(ipw: Any, browser: Any, log: Any = None, label: str = "browser") -> None:
    """invisible_playwright ブラウザを閉じる。Firefox子プロセスも完全kill"""
    import gc

    try:
        browser.close()
    except Exception as _e:
        if log:
            log.write(f"[WARN] {label}.close失敗: {_e}")
    try:
        ipw.stop()  # Playwright.stop()（旧ipw.__exit__）
    except Exception as _e:
        if log:
            log.write(f"[WARN] {label} ipw.__exit__失敗: {_e}")
    # ★ 強化: 残存Firefox子プロセスをOSレベルでkill
    try:
        import signal

        current = psutil.Process()
        for child in current.children(recursive=True):
            try:
                name = child.name().lower()
                if "firefox" in name or "geckodriver" in name or "plugin_container" in name:
                    if log:
                        log.write(f"  [KILL] Firefox子プロセス: {child.pid} ({child.name()})")
                    child.send_signal(signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as _e:
        if log:
            log.write(f"[WARN] 子プロセスkill中エラー: {_e}")
    # ★ メモリ解放
    gc.collect()
    time.sleep(2)
    if log:
        log.write(f"DEBUG: {label} closed (aggressive cleanup)")


# ── 共有ブラウザ関連関数 ──


def create_shared_browser(cfg: dict[str, Any], log: Any = None) -> tuple[Any, Any]:
    """
    1つのInvisiblePlaywright Firefoxを起動し、共有のBrowserオブジェクトを返す。
    引数: cfg（グローバル設定）, log
    戻り値: (ipw, browser)
    seed=None、headless=True、locale='ja-JP', timezone='Asia/Tokyo'
    """
    from invisible_playwright import InvisiblePlaywright

    if log:
        log.write("DEBUG: create_shared_browser – 共有ブラウザ起動")

    # asyncio loop 残留対策
    try:
        asyncio.get_running_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        pass

    # プロキシはここでは設定しない（各コンテキストで個別設定）
    proxy_dict = None
    extra_prefs: dict[str, Any] = {
        # ── Firefoxメモリ制限（cgroup OOM対策）──
        # コンテンツプロセスを1つに制限 → RSS 2-3GB → 500-800MBに削減
        "dom.ipc.processCount": 1,
        "dom.ipc.processCount.max": 1,
        "dom.ipc.processPrelaunch.enabled": False,
        "dom.ipc.keepProcessesAlive.web": 0,
        "javascript.options.mem.max": 256000,  # 256MB JS heap
        "browser.tabs.unloadOnLowMemory": True,  # 低メモリ時タブ解放
        "browser.sessionhistory.max_entries": 10,  # セッション履歴削減
        "browser.sessionhistory.max_total_viewers": 0,  # bfcache完全無効
        "browser.cache.memory.enable": False,  # メモリキャッシュ無効
        "media.peerconnection.enabled": True,  # WebRTC有効（無効化はfingerprint異常と判定されるリスク）
        "media.peerconnection.ice.obfuscate_host_addresses": True,  # 内部IP漏洩防止
        "media.memory_cache_max_size": 2048,  # メディアキャッシュ最小
        # ── BOTセーフな軽量化prefs ──
        "browser.sessionstore.resume_from_crash": False,
        "browser.startup.homepage": "about:blank",
        "datareporting.policy.dataSubmissionEnabled": False,
        "media.autoplay.enabled": False,
        "toolkit.telemetry.reportingpolicy.firstRun": False,
    }
    pin: dict[str, Any] = {}

    ipw = InvisiblePlaywright(
        seed=None,
        headless=True,
        extra_prefs=extra_prefs,
        pin=pin,
        proxy=proxy_dict,
        locale="ja-JP",
        timezone="Asia/Tokyo",
        humanize=True,
    )

    browser: Any = ipw.__enter__()

    if log:
        log.write("DEBUG: 共有ブラウザ起動完了")

    return (ipw, browser)


def create_account_context(
    browser: Any, account_key: str, session_file: str | None = None, log: Any = None
) -> tuple[Any, Any]:
    """
    共有ブラウザ内でアカウント個別のコンテキストとページを作成。

    - proxy は PROXY_MAP から（USE_PROXY=True 且つ account_key が存在する場合）
    - storage_state は session_file または keyringから
    - user_agent/accept-language は FINGERPRINTS から
    - _build_stealth_js でJSステルス層注入
    戻り値: (ctx, page)
    """
    # 指紋取得
    fp: dict[str, Any] | None = FINGERPRINTS.get(account_key) if account_key else None

    # プロキシ
    proxy_str: str | None = None
    if USE_PROXY and account_key in PROXY_MAP:
        proxy_str = PROXY_MAP[account_key]

    # セッション読み込み（ファイル → keyring優先）
    storage = None
    if session_file and os.path.exists(session_file):
        try:
            with open(session_file, encoding="utf-8") as f:
                storage = json.load(f)
        except Exception as e:
            if log:
                log.write(f"WARN: session file read error: {e}")
    if account_key:
        from kensho.utils.keyring import load_session as _kr_load

        kr_data = _kr_load(account_key)
        if kr_data:
            storage = kr_data
            if log:
                log.write("  [KEYRING] Session loaded from Credential Manager")

    # コンテキスト設定
    ctx_kwargs: dict[str, Any] = {
        "storage_state": storage,
    }
    if proxy_str:
        ctx_kwargs["proxy"] = {"server": proxy_str}
    if fp:
        ctx_kwargs["user_agent"] = fp["user_agent"]
        accept_lang = fp.get("accept_language", "ja-JP,ja;q=0.9,en-US;q=0.8")
        ctx_kwargs["extra_http_headers"] = {
            "Accept-Language": accept_lang,
        }

    ctx = browser.new_context(**ctx_kwargs)

    # ★ ページ取得：永続コンテキストの既存ページ or 新規作成
    pages = ctx.pages
    if pages:
        page = pages[0]
        if log:
            log.write("DEBUG: using existing page from persistent context")
    else:
        page = ctx.new_page()
        if log:
            log.write("DEBUG: created new page")

    if fp:
        set_viewport_for_fingerprint(page, fp)
    else:
        random_viewport(page)

    page.set_default_timeout(60000)  # ページ操作の最大待機時間

    # JSステルス層注入
    js_code = _build_stealth_js(fp)
    page.add_init_script(js_code)

    if log:
        log.write(f"DEBUG: create_account_context – {account_key}")

    return (ctx, page)


def close_shared_browser(ipw: Any, browser: Any, log: Any = None) -> None:
    """共有ブラウザを閉じる。Firefox子プロセスも完全kill"""
    close_browser(ipw, browser, log, label="shared_browser")
