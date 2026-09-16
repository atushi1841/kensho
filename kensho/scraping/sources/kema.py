"""ke-ma.net（懸賞マニア）— オープン懸賞ページからX URLを直接収集"""

from __future__ import annotations

import re
import time
from typing import Any

from .common import HEADERS, fetch, has_skip_keyword

# ── 第5収集源: ke-ma.net（懸賞マニア）──
_KEMA_BASE: str = "https://ke-ma.net"
# オープン懸賞一覧の最大ページ（v69検証: /open/page/N/ で13ページ以上にページネーション）
_KEMA_MAX_PAGES: int = 15
# ページ間の待機秒（BOT対策: 人間らしい操作を模倣）
_KEMA_PAGE_SLEEP: float = 0.6


# ページ番号→一覧URL（1ページ目は /open/ 本体、2ページ目以降は /open/page/N/）
def _kema_list_url(page: int) -> str:
    return _KEMA_BASE + "/open/" if page <= 1 else f"{_KEMA_BASE}/open/page/{page}/"


def scrape_kema(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """ke-ma.net のオープン懸賞ページからX URLを直接収集。複数ページを巡回。
    一覧ページにX URLが直接記載されているため1段階で取得可能。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()
    empty_pages: int = 0

    for page in range(1, _KEMA_MAX_PAGES + 1):
        if page > 1:
            time.sleep(_KEMA_PAGE_SLEEP)

        try:
            code, html, _ = fetch(_kema_list_url(page))
            if code != 200:
                out(f"  [KEMA] ページ{page}: HTTP {code} - 終了")
                break

            x_urls: list[str] = re.findall(r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+", html)
            if not x_urls:
                out(f"  [KEMA] ページ{page}: Xリンクなし - 終了")
                break

            page_new: int = 0
            for x_url in x_urls:
                if x_url in seen_x_urls or x_url in processed_set:
                    continue
                seen_x_urls.add(x_url)
                page_new += 1

                # 締切日抽出
                deadline: str = ""
                pos: int = html.find(x_url)
                ctx: str = ""
                if pos > 0:
                    ctx = html[max(0, pos - 1200) : min(len(html), pos + 400)]
                    # YYYY年M月D日
                    dm = re.search(r"(202\d)[年/](\d{1,2})[月/](\d{1,2})", ctx)
                    if dm:
                        deadline = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                    else:
                        # M月D日 (締切キーワード前後)
                        dm = re.search(r"(\d{1,2})月(\d{1,2})日", ctx)
                        if dm:
                            deadline = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"
                        else:
                            # M/D
                            dm = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", ctx)
                            if dm and 1 <= int(dm.group(1)) <= 12 and 1 <= int(dm.group(2)) <= 31:
                                deadline = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"

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
                items.append({
                    "detail_url": f"/kema/open/{len(items)}",
                    "x_url": x_url,
                    "source": "kema",
                    "time": 0.0,
                    "deadline": deadline,
                    "winner_count": winner_count,
                    "days_remaining": "",
                    "applied": applied,
                    "keyword_flag": has_skip_keyword(ctx),
                })
                out(f"    ✅ {x_url[:65]}...")

            out(f"  [KEMA] ページ{page}: 走査{len(x_urls)}件(新規{page_new}、収集件数ではない)")
            if page_new == 0:
                empty_pages += 1
            else:
                empty_pages = 0
            if empty_pages >= 2:
                out(f"  [KEMA] 新規なし連続{empty_pages}ページ - 終了")
                break
        except Exception as e:
            out(f"  [KEMA] ページ{page}: ERROR {type(e).__name__}: {e}")
            break

    out(f"  [KEMA] 計{len(items)}件取得")
    return items
