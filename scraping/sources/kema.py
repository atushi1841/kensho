"""ke-ma.net（懸賞マニア）— オープン懸賞ページからX URLを直接収集"""
from __future__ import annotations

import re
from typing import Any

from .common import HEADERS, fetch, has_skip_keyword

# ── 第5収集源: ke-ma.net（懸賞マニア）──
_KEMA_BASE: str = "https://ke-ma.net"


def scrape_kema(
    out: Any, processed_set: set[str], account_keys: list[str]
) -> list[dict[str, Any]]:
    """ke-ma.net のオープン懸賞ページからX URLを直接収集。
    一覧ページにX URLが直接記載されているため1段階で取得可能。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    # /open/ ページのみ（X懸賞が集中）
    try:
        code, html, _ = fetch(f"{_KEMA_BASE}/open/")
        if code != 200:
            out(f"  [KEMA] HTTP {code} - スキップ")
            return items

        x_urls: list[str] = re.findall(
            r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+", html
        )
        if not x_urls:
            out("  [KEMA] Xリンクなし")
            return items

        for x_url in x_urls:
            if x_url in seen_x_urls or x_url in processed_set:
                continue
            seen_x_urls.add(x_url)

            # 締切日抽出
            deadline: str = ""
            pos: int = html.find(x_url)
            ctx: str = ""
            if pos > 0:
                ctx = html[max(0, pos - 600) : pos]
                dm = re.search(
                    r"[締〆]切[：:]?\s*(\d{4})[年/](\d{1,2})[月/](\d{1,2})日", ctx
                )
                if dm:
                    deadline = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                else:
                    dm2 = re.search(r"(\d{1,2})月(\d{1,2})日[^\d]*?[締〆]切", ctx)
                    if dm2:
                        deadline = f"2026-{int(dm2.group(1)):02d}-{int(dm2.group(2)):02d}"

            # 当選人数
            winner_count: int = 0
            if pos > 0:
                wm = re.search(r"(\d[\d,]*)\s*名", ctx)
                if wm:
                    try:
                        winner_count = int(wm.group(1).replace(",", ""))
                    except ValueError:
                        pass

            applied: dict[str, None] = {k: None for k in account_keys}
            items.append(
                {
                    "detail_url": f"/kema/open/{len(items)}",
                    "x_url": x_url,
                    "source": "kema",
                    "time": 0.0,
                    "deadline": deadline,
                    "winner_count": winner_count,
                    "days_remaining": "",
                    "applied": applied,
                    "keyword_flag": has_skip_keyword(ctx),
                }
            )
            out(f"    ✅ {x_url[:65]}...")

        out(f"  [KEMA] {len(items)}件取得")
    except Exception as e:
        out(f"  [KEMA] ERROR {type(e).__name__}: {e}")

    return items
