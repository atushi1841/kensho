"""chance.com (チャンスイット) — X(Twitter)懸賞一覧から収集"""

from __future__ import annotations

import random
import re
import time
from typing import Any

import httpx

from .common import HEADERS, _fetch_with_retry, has_skip_keyword

_CHANCE_BASE = "https://www.chance.com"
_LIST_URL = f"{_CHANCE_BASE}/present/list/x-twitter-entry/"
# レート制限が厳しいため最大2ページ（約40件）に制限
_MAX_PAGES = 2

# モジュールレベルのhttpx.Client（使い回しで接続プール活用＋sleep削減）
_HTTPX_CLIENT: httpx.Client | None = None
_X_HEADERS: dict[str, str] = {
    **HEADERS,
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}
_HTTP_RE: re.Pattern = re.compile(r"https?://(?:x|twitter)\.com/.+/status/\d+")


def _resolve_x_url(jump_url: str) -> str | None:
    """jump.srv の302リダイレクトから X URL を解決。
    Client は再利用（接続プール＋TCP keepalive で高速化）。"""
    global _HTTPX_CLIENT
    if _HTTPX_CLIENT is None:
        _HTTPX_CLIENT = httpx.Client(follow_redirects=True, timeout=15)
    try:
        r = _HTTPX_CLIENT.get(jump_url, headers=_X_HEADERS)
        final = str(r.url)
        if _HTTP_RE.search(final):
            return final
    except Exception:
        pass
    return None


def scrape_chancecom(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """chance.com の X(Twitter)懸賞一覧から収集。
    一覧ページ→detailページ→jump.srv→X URL の3段階。
    レート制限対策のため各リクエスト間に長めの遅延を入れる。
    """
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    # ── Step 1: 一覧ページをスキャン ──
    detail_urls: list[str] = []
    for page in range(_MAX_PAGES):
        url = _LIST_URL if page == 0 else f"{_LIST_URL}?page={page + 1}&order=1"
        try:
            time.sleep(random.uniform(0.5, 1.0))
            code, html, _ = _fetch_with_retry(url, timeout=20)
            if code in (503, 429):
                out(f"  [CHANCE] ページ{page + 1}: レート制限({code}) → 一時停止")
                time.sleep(10)
                continue
            if code != 200:
                out(f"  [CHANCE] ページ{page + 1}: HTTP {code}")
                break
            found = re.findall(r'href="(https://www\.chance\.com/present/detail/\d+/?)', html)
            if not found:
                out(f"  [CHANCE] ページ{page + 1}: detailリンクなし → 終了")
                break
            detail_urls.extend(found)
            out(f"  [CHANCE] ページ{page + 1}: {len(found)}件 (累計{len(detail_urls)}件)")
        except Exception as e:
            out(f"  [CHANCE] ページ{page + 1}: ERROR {e}")
            break
    out(f"  [CHANCE] detail URL 計{len(detail_urls)}件")

    # ── Step 2: 各detailページから情報抽出 ──
    for idx, detail_url in enumerate(detail_urls):
        detail_path = "/" + "/".join(detail_url.rstrip("/").split("/")[-3:]) + "/"
        if detail_path in processed_set:
            continue
        try:
            time.sleep(random.uniform(1.0, 2.5))
            code, html, _ = _fetch_with_retry(detail_url, timeout=20)
            if code in (503, 429):
                out(f"  [CHANCE] detail {idx + 1}/{len(detail_urls)}: レート制限 → 終了")
                break
            if code != 200:
                continue

            # 2026-09: サイト側が &s= トークンを廃止 → 互換のため任意匹配（旧形式も許容）
            jump_match = re.search(r"(https://www\.chance\.com/jump\.srv\?id=\d+(?:&s=[a-zA-Z0-9]+)?)", html)
            if not jump_match:
                continue
            jump_url = jump_match.group(1)

            x_url = _resolve_x_url(jump_url)
            if not x_url:
                continue
            if x_url in seen_x_urls or x_url in processed_set:
                continue
            seen_x_urls.add(x_url)

            deadline = ""
            dm = re.search(r"<dt>応募締切</dt><dd>(\d{1,2})/(\d{1,2})", html)
            if dm:
                deadline = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"

            winner_count = 0
            wm = re.search(r"<dt>当選者数</dt><dd><span>(\d[\d,]*)名様</span>", html)
            if wm:
                try:
                    winner_count = int(wm.group(1).replace(",", ""))
                except ValueError:
                    pass

            applied: dict[str, None] = {k: None for k in account_keys}
            items.append({
                "detail_url": detail_path,
                "x_url": x_url,
                "source": "chancecom",
                "time": 0.0,
                "deadline": deadline,
                "winner_count": winner_count,
                "days_remaining": "",
                "applied": applied,
                "keyword_flag": has_skip_keyword(html),
            })
            out(f"    ✅ {x_url[:70]}...")

        except Exception as e:
            out(f"  [CHANCE] ERROR {detail_path}: {e}")

    out(f"  [CHANCE] 計{len(items)}件")
    return items
