"""kensho-everyday.com（WordPress懸賞ブログ）— X懸賞カテゴリRSSから記事を収集"""

from __future__ import annotations

import re
import time
from typing import Any

from .common import HEADERS, _fetch_with_retry, fetch, has_skip_keyword

# ── 第5b収集源: kensho-everyday.com ──
_KENSHO_EVERY_BASE: str = "https://kensho-everyday.com"
# X懸賞カテゴリのRSSフィード（クローズド懸賞・LINE応募などを除外しX懸賞のみ収集）
# カテゴリ: 懸賞情報 > 応募方法 > SNS懸賞 > Twitter懸賞
_KENSHO_EVERY_RSS: str = (
    "https://kensho-everyday.com/archives/category/"
    "%E6%87%B8%E8%B3%9E%E6%83%85%E5%A0%B1/%E5%BF%9C%E5%8B%9F%E6%96%B9%E6%B3%95/"
    "sns%E6%87%B8%E8%B3%9E/twitter%E6%87%B8%E8%B3%9E/feed"
)


def scrape_kensho_everyday(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """kensho-everyday.com のX懸賞カテゴリRSS → 各記事 → X URL抽出の2段階。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    # ── RSSフィード取得（X懸賞カテゴリ限定・軽量）──
    try:
        code, rss_html, _ = fetch(_KENSHO_EVERY_RSS)
        if code != 200:
            out(f"  [KENS-EVERY] RSS: HTTP {code} - 終了")
            return items
    except Exception as e:
        out(f"  [KENS-EVERY] RSS: ERROR {type(e).__name__}: {e}")
        return items

    # RSSから記事URLを抽出（チャンネルリンク https://kensho-everyday.com は archives/ 不一致で除外される）
    article_links: list[str] = list(
        dict.fromkeys(re.findall(r"<link>\s*(https://kensho-everyday\.com/archives/\d+)\s*</link>", rss_html))
    )
    if not article_links:
        out("  [KENS-EVERY] RSS: 記事リンクなし - 終了")
        return items

    out(f"  [KENS-EVERY] RSS: 記事走査{len(article_links)}件（収集件数ではない）")

    for article_url in article_links:
        try:
            code2, html2, _ = _fetch_with_retry(article_url, referer=_KENSHO_EVERY_BASE, timeout=15)
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

            # 締切日抽出（「締切」「応募期限」など複数パターン）
            deadline: str = ""
            dm = re.search(
                r"[締〆]切[：:]?\s*(?:.*?)?(\d{4})[年/](\d{1,2})[月/](\d{1,2})日",
                html2,
                re.DOTALL,
            )
            if dm:
                deadline = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
            else:
                dm2 = re.search(
                    r"応募期限[：:]?\s*(\d{4})[年/](\d{1,2})[月/](\d{1,2})日",
                    html2,
                    re.DOTALL,
                )
                if dm2:
                    deadline = f"{dm2.group(1)}-{int(dm2.group(2)):02d}-{int(dm2.group(3)):02d}"
                else:
                    dm3 = re.search(
                        r"(\d{1,2})月(\d{1,2})日[^<>]*?[締〆]切",
                        html2,
                        re.DOTALL,
                    )
                    if dm3:
                        deadline = f"2026-{int(dm3.group(1)):02d}-{int(dm3.group(2)):02d}"

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
            detail_url: str = f"/kensho-everyday/archives/{article_id}"
            items.append({
                "detail_url": detail_url,
                "x_url": x_url,
                "source": "kensho-everyday",
                "time": 0.0,
                "deadline": deadline,
                "winner_count": winner_count,
                "days_remaining": "",
                "applied": applied,
                "keyword_flag": has_skip_keyword(html2),
            })
            out(f"    ✅ {x_url[:65]}...")
        except Exception as e:
            out(f"    [WARN] kensho-everyday記事処理失敗: {e}")

        time.sleep(0.3)  # レート制限回避（記事間0.3秒）

    out(f"  [KENS-EVERY] 計{len(items)}件取得")
    return items
