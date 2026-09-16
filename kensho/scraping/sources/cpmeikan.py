"""cp.meikan.org（キャンペーン名鑑）— Xキャンペーン一覧からX URLを直接収集"""

from __future__ import annotations

import re
import time
from typing import Any

from .common import HEADERS, fetch, has_skip_keyword

# ── 第4収集源: cp.meikan.org（キャンペーン名鑑）──
_CPMEIKAN_BASE: str = "https://cp.meikan.org/xcp"


def scrape_cpmeikan(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """cp.meikan.org のXキャンペーン一覧からX URLを直接収集。
    一覧ページにX URLが直接記載されているため1段階で取得可能。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    for page_num in range(1, 11):  # 最大10ページ
        page_url: str = _CPMEIKAN_BASE
        if page_num > 1:
            page_url = f"{_CPMEIKAN_BASE}/{page_num}/"

        try:
            code, html, _ = fetch(page_url)
            if code != 200:
                out(f"  [CPMK] ページ{page_num}: HTTP {code} - 終了")
                break

            # X URLを直接抽出（/i/web/status/ 形式にも対応。2026-08-20サイト形式変更で /i/web/ のみに）
            x_urls_raw: list[str] = re.findall(r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+", html)
            _iweb: list[str] = re.findall(
                r"(?:data-tweet-url=\"|href=\")(https?://(?:x|twitter)\.com/i/web/status/\d+)", html
            )
            x_urls_raw += _iweb
            # 一意化（順序維持）
            x_urls = list(dict.fromkeys(x_urls_raw))
            if not x_urls:
                out(f"  [CPMK] ページ{page_num}: Xリンクなし - 終了")
                break

            for x_url in x_urls:
                if x_url in seen_x_urls or x_url in processed_set:
                    continue
                seen_x_urls.add(x_url)

                # 各キャンペーンの締切日を周辺テキストから抽出
                deadline: str = ""
                pos: int = html.find(x_url)
                context: str = ""
                if pos > 0:
                    context = html[max(0, pos - 1200) : min(len(html), pos + 400)]
                    # YYYY年M月D日 (最優先)
                    dm = re.search(r"(202\d)[年/](\d{1,2})[月/](\d{1,2})", context)
                    if dm:
                        deadline = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                    else:
                        # M月D日
                        dm = re.search(r"(\d{1,2})月(\d{1,2})日", context)
                        if dm:
                            deadline = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"
                        else:
                            # M/D or YYYY-MM-DD
                            dm = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", context)
                            if dm and 1 <= int(dm.group(1)) <= 12 and 1 <= int(dm.group(2)) <= 31:
                                deadline = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"
                            else:
                                dm = re.search(r"(202\d)-(\d{1,2})-(\d{1,2})", context)
                                if dm:
                                    deadline = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"

                winner_count: int = 0
                if pos > 0:
                    wm2 = re.search(r"(\d[\d,]*)\s*名", context)
                    if wm2:
                        try:
                            winner_count = int(wm2.group(1).replace(",", ""))
                        except ValueError:
                            pass

                applied: dict[str, None] = {k: None for k in account_keys}
                detail_url: str = f"/cpmeikan/xcp/{page_num}/{len(items)}"
                items.append({
                    "detail_url": detail_url,
                    "x_url": x_url,
                    "source": "cpmeikan",
                    "time": 0.0,
                    "deadline": deadline,
                    "winner_count": winner_count,
                    "days_remaining": "",
                    "applied": applied,
                    "keyword_flag": has_skip_keyword(context),
                })
                out(f"    ✅ {x_url[:65]}...")

            out(f"  [CPMK] ページ{page_num}: 走査{len(x_urls)}件（収集件数ではない）")
            time.sleep(0.3)

        except Exception as e:
            out(f"  [CPMK] ページ{page_num}: ERROR {type(e).__name__}: {e}")
            break

    out(f"  [CPMK] 計{len(items)}件取得")
    return items
