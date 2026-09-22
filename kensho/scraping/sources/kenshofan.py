"""kenshofan.com（懸賞ファン）— X/Twitter懸賞一覧からX URLを直接収集
一覧ページにX URLが直接記載されているため1段階で取得可能。
cp.meikan.org と同様のシンプルな構造で、バグが出にくい。
戻り値: collected.json 互換のアイテムリスト。
"""

from __future__ import annotations
import re
import time
from typing import Any

from .common import HEADERS, _fetch_with_retry, has_skip_keyword

# ── 第5収集源: kenshofan.com（懸賞ファン）──
_KENSHOFANA_BASE: str = "https://kenshofan.com"
_KENSHOFANA_MAX_PAGES: int = 20


def scrape_kenshofan(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """kenshofan.com のX/Twitter懸賞一覧からX URLを直接収集。
    一覧ページにX URLが直接記載されているため1段階で取得可能。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    for page in range(1, _KENSHOFANA_MAX_PAGES + 1):
        if page == 1:
            list_url: str = _KENSHOFANA_BASE
        else:
            list_url: str = f"{_KENSHOFANA_BASE}/page/{page}"

        try:
            # リストページ取得（指数バックオフ付きリトライ）
            code, html, _ = _fetch_with_retry(list_url, timeout=30, source="kenshofan")
            if code != 200:
                out(f"  [KFAN] ページ{page}: HTTP {code} - 終了")
                break

            # X URLを直接抽出（/status/ 形式）
            x_urls_raw: list[str] = re.findall(
                r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+",
                html,
            )

            # 一意化（順序維持）
            x_urls: list[str] = list(dict.fromkeys(x_urls_raw))

            if not x_urls:
                out(f"  [KFAN] ページ{page}: Xリンクなし - 終了")
                break

            out(f"  [KFAN] ページ{page}: 走査{x_urls}件（収集件数ではない）")

            for x_url in x_urls:
                if x_url in seen_x_urls or x_url in processed_set:
                    continue
                seen_x_urls.add(x_url)

                # 締切日を周辺テキストから抽出
                deadline: str = ""
                # X URLの周辺テキストを検索
                x_pos: int = html.find(x_url)
                if x_pos > 0:
                    context: str = html[
                        max(0, x_pos - 800) : min(len(html), x_pos + 400)
                    ]
                    # YYYY年M月D日 (最優先)
                    dm = re.search(r"(202\d)[年/](\d{1,2})[月/](\d{1,2})日", context)
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

                winner_count: int = 0
                wm = re.search(r"(\d[\d,]*)\s*名様", context)
                if wm:
                    try:
                        winner_count = int(wm.group(1).replace(",", ""))
                    except ValueError:
                        pass

                applied: dict[str, None] = {k: None for k in account_keys}

                # 記事ID/詳細URLの抽出（ページ番号と順序から生成）
                article_id: str = str(page) + "_" + str(len(items))
                detail_url: str = f"/kenshofan/page/{page}/{len(items)}"

                items.append(
                    {
                        "detail_url": detail_url,
                        "x_url": x_url,
                        "source": "kenshofan",
                        "time": 0.0,
                        "deadline": deadline,
                        "winner_count": winner_count,
                        "days_remaining": "",
                        "applied": applied,
                        "keyword_flag": has_skip_keyword(context),
                    }
                )
                out(f"    ✅ {x_url[:65]}...")

            out(f"  [KFAN] ページ{page}: 完了({len(x_urls)}件走査)")
            time.sleep(0.3)  # 優しめの間隔

        except Exception as e:
            out(f"  [KFAN] ページ{page}: ERROR {type(e).__name__}: {e}")
            break

    out(f"  [KFAN] 計{len(items)}件取得")
    return items