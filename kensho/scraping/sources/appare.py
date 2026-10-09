"""appare.com（懸賞天晴）— X懸賞を収集

サイト構造:
- 一覧: search-category.cgi?mode=1new&page=N  （1ページ10件、Shift_JISエンコーディング）
- 詳細: search-category.cgi?links=<id>        （og:url でX URLを取得）
- robots.txt: 不存在（404）。許容範囲と判断。
- TOS: 公式サイトに明示的なロボットポリシーなし。公開情報の収集自体は問題なし。
  ただしX URL取得率は~15%と低め。

注意点:
- ページングは hidden input の page value から「次の10件表示」ボタンの有無で判定。
  page=11 以降は空または404になるのでそれまで巡回。
- エンコーディングは Shift_JIS。
- 締切日は一覧ページ（search-category.cgi?mode=1new）に MM/DD 形式で記載されている場合あり。
  詳細ページには期限情報がないため、一覧ページから取得する必要がある。
"""

from __future__ import annotations

import re
import time
from typing import Any

from .common import HEADERS, _fetch_with_retry, has_skip_keyword

# ── 新規収集源: appare.com（懸賞天晴）──
_APPARE_BASE: str = "https://www.appare.com"
_APPARE_LIST_PAGE_SIZE: int = 10  # 1ページ10件


def _list_url(page: int) -> str:
    if page == 1:
        return f"{_APPARE_BASE}/search-category.cgi?mode=1new"
    return f"{_APPARE_BASE}/search-category.cgi?mode=1new&page={page}"


def _detail_url(link_id: str) -> str:
    return f"{_APPARE_BASE}/search-category.cgi?links={link_id}"


def _decode_appare(data: str) -> str:
    """appare.com は Shift_JIS エンコーディング。httpx が自動デコードできない場合のフォールバック。
    既に str なのでエンコーディング推定のみ実行。"""
    # _fetch_with_retry は httpx で既に str にデコード済みのため、この関数は
    # エンコーディング推定が失敗した場合に再試行するために存在する。
    # 通常はそのまま data を返す。
    return data


def _extract_deadline_from_listing(html: str) -> str:
    """一覧ページの MM/DD 形式の締切を抽出。當年補完。"""
    # 例: 10/09, 10/17 など
    m = re.search(r"(\d{1,2})/(\d{1,2})(?!\d)", html)
    if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
        return f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def _extract_x_url(html: str) -> str | None:
    """og:url または /status/<id> 形式のX URLを抽出。"""
    og = re.findall(r'property="og:url"\s+content="(https://x\.com/[^\"]+)"', html)
    if og:
        return og[0]
    urls = re.findall(r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+", html)
    return urls[0] if urls else None


def _extract_title(html: str) -> str:
    """賞品タイトルを抽出。"""
    # <font size=4><a ...>タイトル</a></font> 形式
    m = re.search(r'<font size=4><a[^>]*>([^<]+)</a>', html)
    if m:
        return m.group(1).strip()
    # ID:NNNN の次の行
    m = re.search(r"ID:\d+\s*<br[^>]*><small>賞品:\s*<small><b><font size=4><a[^>]*>([^<]+)</a>", html)
    if m:
        return m.group(1).strip()
    return ""


def scrape_appare(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """appare.com のX懸賞を収集。
    一覧ページを巡回 → 各記事詳細ページfetch → X URL（og:url）を抽出。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    for page in range(1, 12):  # 11ページまで（2026-10-09実測: 12ページ目以降はX懸賞ヒット0件のため打切り）
        list_url = _list_url(page)
        try:
            code, html, _ = _fetch_with_retry(list_url, timeout=30, source="appare")
            if code != 200:
                out(f"  [APPR] ページ{page}: HTTP {code} - 終了")
                break

            # 記事リンクを抽出（search-category.cgi?links=<id>）
            link_ids: list[str] = list(dict.fromkeys(
                re.findall(r'href="search-category\.cgi\?links=(\d+)"', html)
            ))
            if not link_ids:
                out(f"  [APPR] ページ{page}: 記事リンクなし - 終了")
                break

            out(f"  [APPR] ページ{page}: 記事走査{len(link_ids)}件")

            for link_id in link_ids:
                try:
                    detail_url = _detail_url(link_id)
                    code2, html2, final_url2 = _fetch_with_retry(detail_url, referer=list_url, timeout=30, source="appare")

                    # appare.com 詳細ページは 302 + body内meta refreshにX URL（2026-10-09実測:
                    # code=302, final_urlは appare.com のまま, body に <meta refresh=...x.com/...>）
                    x_url = None
                    if code2 in (200, 302):
                        x_url = _extract_x_url(html2)
                    if not x_url and re.match(r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+", final_url2 or ""):
                        x_url = final_url2
                    if not x_url:
                        continue
                    norm_x = re.sub(r"https?://(?:x|twitter)\.com/", "x.com/", x_url).split("#")[0].split("?")[0].rstrip("/")
                    # processed_set は生URL形式（https://x.com/...）で蓄積されるため両方照合する
                    if norm_x in seen_x_urls or x_url in processed_set or norm_x in processed_set:
                        continue
                    seen_x_urls.add(norm_x)

                    title = _extract_title(html2)
                    # 一覧ページから締切を推定（同一ページ内ならリストから取得）
                    deadline = _extract_deadline_from_listing(html)
                    # 当選人数は詳細ページから
                    winner_m = re.search(r"(\d[,\d]*)\s*名", html2)
                    winner_count = int(winner_m.group(1).replace(",", "")) if winner_m else 0

                    kctx: str = ""
                    _pos = html2.find(x_url)
                    if _pos > 0:
                        kctx = html2[max(0, _pos - 800) : min(len(html2), _pos + 300)]

                    applied: dict[str, None] = {k: None for k in account_keys}
                    item = {
                        "detail_url": f"/appare/links/{link_id}",
                        "x_url": x_url,
                        "source": "appare",
                        "time": 0.0,
                        "deadline": deadline,
                        "winner_count": winner_count,
                        "days_remaining": "",
                        "applied": applied,
                        "keyword_flag": has_skip_keyword(kctx),
                        "tweet_text": title,
                    }
                    items.append(item)
                    out(f"    ✅ {x_url[:65]}...")
                except Exception as e:
                    out(f"    [WARN] appare link={link_id} 失敗: {e}")

            if len(link_ids) < _APPARE_LIST_PAGE_SIZE:
                break
            time.sleep(0.4)

        except Exception as e:
            out(f"  [APPR] ページ{page}: ERROR {type(e).__name__}: {e}")
            break

    out(f"  [APPR] 計{len(items)}件取得")
    return items
