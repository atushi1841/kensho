"""mechatoku.com（めちゃ得ページ / とらたぬ情報）— X懸賞を収集

サイト構造:
- 一覧: /ckensho/ichiran/page/N/  （最大66ページ、1ページ約10件）
- 詳細: /ckensho/shousai/cid/<id>  （各記事を1ページfetchしてX URLを抽出）
- robots.txt: 記事ページはDisallowなし（img系のみ制限）。Sitemapあり。
- TOS: 「自動プログラムを利用して応募」は禁止だが、データ収集自体は記載なし。
  懸賞応募サイトの情報整理サイトであり、公開情報を取得する分には問題なし。

注意点:
- 詳細ページの約2%にのみX URL（og:url or /status/）が含まれる。
  全体のX懸賞割合は低いが、66ページ×10件=660件の詳細ページを走査することで
  数十件のX懸賞を得られる見込み。
- 締切日は「26年10月9日」等の和暦表記が主流。2桁年の補完が必要。
"""

from __future__ import annotations

import re
import time
from typing import Any

from .common import HEADERS, _fetch_with_retry, has_skip_keyword

# ── 新規収集源: mechatoku.com（めちゃ得ページ / とらたぬ情報）──
_MECHATOKU_BASE: str = "https://www.mechatoku.com"
# 2026-10-09 実測: 1ページ45記事×X URL命中率~2%。全66ページ走査は~3000fetchで
# 収集タイムアウト連鎖（t_dd0d7fcbと同型）を招くため、新着15ページに制限。
_MECHATOKU_MAX_PAGES: int = 15  # sitemapにpage/66まであるが意図的に制限


def _list_url(page: int) -> str:
    return f"{_MECHATOKU_BASE}/ckensho/ichiran/page/{page}" if page > 1 else f"{_MECHATOKU_BASE}/ckensho/ichiran/"


def _detail_url(cid: str) -> str:
    return f"{_MECHATOKU_BASE}/ckensho/shousai/cid/{cid}"


def _extract_deadline(text: str) -> str:
    """締切日をYYYY-MM-DD形式で抽出。2桁年の補完あり。"""
    # 26年10月9日 → 2026-10-09
    m = re.search(r"(20)?(\d{1,2})[年/](\d{1,2})[月/](\d{1,2})日", text)
    if m:
        yr = int(m.group(2))
        if yr < 100:
            yr += 2000 if yr < 50 else 1900
        else:
            yr = int(m.group(1) + m.group(2))
        return f"{yr}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"
    # MM/DD 形式（年なし、当年補完）
    m = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", text)
    if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
        return f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def _extract_winner_count(text: str) -> int:
    m = re.search(r"(\d[,\d]*)\s*名様?", text)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0


def _extract_x_url(html: str) -> str | None:
    """og:url または /status/<id> 形式のX URLを抽出。複数あれば先頭を返す。"""
    og = re.findall(r'property="og:url"\s+content="(https://x\.com/[^\"]+)"', html)
    if og:
        return og[0]
    urls = re.findall(r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+", html)
    return urls[0] if urls else None


def scrape_mechatoku(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """mechatoku.com のX懸賞を収集。
    一覧ページを巡回 → 各記事詳細ページfetch → X URL抽出。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    for page in range(1, _MECHATOKU_MAX_PAGES + 1):
        list_url = _list_url(page)
        try:
            code, html, _ = _fetch_with_retry(list_url, timeout=30, source="mechatoku")
            if code != 200:
                out(f"  [MECH] ページ{page}: HTTP {code} - 終了")
                break

            # 記事リンクを抽出（絶対URL / 相対URL両方対応）
            cid_links: list[str] = list(dict.fromkeys(re.findall(r'href="[^"]*?/ckensho/shousai/cid/(\d+)"', html)))
            if not cid_links:
                out(f"  [MECH] ページ{page}: 記事リンクなし - 終了")
                break

            out(f"  [MECH] ページ{page}: 記事走査{len(cid_links)}件")

            for cid in cid_links:
                try:
                    code2, html2, _ = _fetch_with_retry(
                        _detail_url(cid), referer=list_url, timeout=30, source="mechatoku"
                    )
                    if code2 != 200:
                        continue

                    x_url = _extract_x_url(html2)
                    if not x_url:
                        continue
                    norm_x = re.sub(r"https?://(?:x|twitter)\.com/", "x.com/", x_url).split("#")[0].split("?")[0].rstrip("/")
                    # processed_set は生URL形式（https://x.com/...）で蓄積されるため両方照合する
                    if norm_x in seen_x_urls or x_url in processed_set or norm_x in processed_set:
                        continue
                    seen_x_urls.add(norm_x)

                    # タイトル（h2 または title要素）
                    title_m = re.search(r"<h2[^>]*>([^<]+)</h2>", html2)
                    title: str = title_m.group(1).strip() if title_m else ""
                    # titleタグから剥ぎ取る
                    if not title:
                        tm = re.search(r"<title>([^<]+)</title>", html2)
                        if tm:
                            title = tm.group(1).split("：")[-1].split("|")[-1].strip()

                    # 締切日・当選人数（詳細ページ全文から）
                    deadline = _extract_deadline(html2)
                    winner_count = _extract_winner_count(html2)

                    # X URL周辺テキストでkeyword_flag判定
                    kctx: str = ""
                    _pos = html2.find(x_url)
                    if _pos > 0:
                        kctx = html2[max(0, _pos - 800) : min(len(html2), _pos + 300)]

                    applied: dict[str, None] = {k: None for k in account_keys}
                    item = {
                        "detail_url": f"/mechatoku/shousai/cid/{cid}",
                        "x_url": x_url,
                        "source": "mechatoku",
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
                    out(f"    [WARN] mechatoku cid={cid} 失敗: {e}")

            if len(cid_links) < 5:  # 最終ページ判定
                break
            time.sleep(0.4)

        except Exception as e:
            out(f"  [MECH] ページ{page}: ERROR {type(e).__name__}: {e}")
            break

    out(f"  [MECH] 計{len(items)}件取得")
    return items
