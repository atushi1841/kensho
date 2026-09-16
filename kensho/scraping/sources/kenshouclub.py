"""kenshou.club（懸賞CLUB）— X/Twitter懸賞一覧からX URLを収集"""

from __future__ import annotations

import re
import time
from typing import Any

from .common import HEADERS, _fetch_with_retry, fetch, has_skip_keyword

# ── 第3収集源: kenshou.club（懸賞CLUB）──
_KENSHOUCLUB_BASE: str = "https://kenshou.club"
_KENSHOUCLUB_TAG: str = "/archives/tag/twitter%E3%81%A7%E5%BF%9C%E5%8B%9F"
_KENSHOUCLUB_MAX_PAGES: int = 24


def scrape_kenshouclub(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """kenshou.club のX/Twitter懸賞一覧からX URLを収集。
    一覧ページ → 各記事ページ → X URL抽出 の2段階。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    for page in range(1, _KENSHOUCLUB_MAX_PAGES + 1):
        list_url: str = f"{_KENSHOUCLUB_BASE}{_KENSHOUCLUB_TAG}"
        if page > 1:
            list_url = f"{_KENSHOUCLUB_BASE}{_KENSHOUCLUB_TAG}/page/{page}"

        try:
            code, html, _ = fetch(list_url)
            if code != 200:
                out(f"  [KCLUB] ページ{page}: HTTP {code} - 終了")
                break

            # 記事リンクを抽出（カテゴリ系は除外）
            article_links: list[str] = []
            for m in re.finditer(r"href=\"(https://kenshou\.club/archives/\d+)\"", html):
                href: str = m.group(1)
                if href not in article_links:
                    article_links.append(href)

            if not article_links:
                out(f"  [KCLUB] ページ{page}: リンクなし - 終了")
                break

            out(f"  [KCLUB] ページ{page}: 記事走査{len(article_links)}件（収集件数ではない）")

            for article_url in article_links:
                try:
                    code2, html2, _ = _fetch_with_retry(article_url, referer=list_url, timeout=15)
                    if code2 != 200:
                        continue

                    # X URL抽出
                    x_urls: list[str] = re.findall(
                        r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+",
                        html2,
                    )
                    if not x_urls:
                        continue
                    x_url = x_urls[0]
                    if x_url in seen_x_urls or x_url in processed_set:
                        continue
                    seen_x_urls.add(x_url)

                    # 締切日抽出
                    deadline: str = ""
                    dm = re.search(
                        r"[締〆]切[：:]?\s*(\d{4})[年/](\d{1,2})[月/](\d{1,2})日",
                        html2,
                    )
                    if dm:
                        deadline = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                    else:
                        dm2 = re.search(r"(\d{1,2})月(\d{1,2})日[^\d]*?[締〆]切", html2)
                        if dm2:
                            deadline = f"2026-{int(dm2.group(1)):02d}-{int(dm2.group(2)):02d}"

                    # 当選人数抽出
                    winner_count: int = 0
                    wm = re.search(r"(\d[\d,]*)\s*名様", html2)
                    if wm:
                        try:
                            winner_count = int(wm.group(1).replace(",", ""))
                        except ValueError:
                            pass

                    applied: dict[str, None] = {k: None for k in account_keys}
                    article_id: str = str(article_url).split("/")[-1]
                    detail_url: str = f"/kenshouclub/archives/{article_id}"
                    # ★ 2026-08-26: 過検出是正 — 記事HTML全体ではなくX URL周辺テキストで判定
                    #   （記事ページのナビ/コメント欄に「コメント」「ページ」等が常にあるため全233件がtrue化していた）
                    kctx: str = ""
                    _kpos: int = html2.find(x_url)
                    if _kpos > 0:
                        kctx = html2[max(0, _kpos - 800) : min(len(html2), _kpos + 300)]
                    items.append({
                        "detail_url": detail_url,
                        "x_url": x_url,
                        "source": "kenshouclub",
                        "time": 0.0,
                        "deadline": deadline,
                        "winner_count": winner_count,
                        "days_remaining": "",
                        "applied": applied,
                        "keyword_flag": has_skip_keyword(kctx),
                    })
                    out(f"    ✅ {x_url[:65]}...")
                except Exception as e:
                    out(f"    [WARN] kenshouclub記事処理失敗: {e}")

            if len(article_links) < 10:  # 最終ページ
                break
            time.sleep(0.5)  # 優しめの間隔

        except Exception as e:
            out(f"  [KCLUB] ページ{page}: ERROR {type(e).__name__}: {e}")
            break

    out(f"  [KCLUB] 計{len(items)}件取得")
    return items
