"""chance.com (チャンスイット) — X(Twitter)懸賞一覧から収集"""
from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin

from .common import HEADERS, fetch, has_skip_keyword

_CHANCE_BASE = "https://www.chance.com"
_LIST_URL = f"{_CHANCE_BASE}/present/list/x-twitter-entry/"
_MAX_PAGES = 20  # 最大20ページ（320件）


def scrape_chancecom(
    out: Any, processed_set: set[str], account_keys: list[str]
) -> list[dict[str, Any]]:
    """chance.com の X(Twitter)懸賞一覧から収集。
    一覧ページ→detailページ→jump.srv→X URL の3段階。
    """
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"

    # ── Step 1: 一覧ページをスキャンして detail URL を収集 ──
    detail_ids: list[str] = []
    for page in range(_MAX_PAGES):
        if page == 0:
            url = _LIST_URL
        else:
            url = f"{_LIST_URL}?page={page}&order=1"
        try:
            code, html, _ = fetch(url)
            if code != 200:
                out(f"  [CHANCE] ページ{page+1}: HTTP {code}")
                break
            # /present/detail/{数字}/ のリンクを抽出
            found = re.findall(r'href="(/present/detail/\d+/?)', html)
            if not found:
                out(f"  [CHANCE] ページ{page+1}: detailリンクなし → 終了")
                break
            detail_ids.extend(found)
            out(f"  [CHANCE] ページ{page+1}: {len(found)}件 (累計{len(detail_ids)}件)")
        except Exception as e:
            out(f"  [CHANCE] ページ{page+1}: ERROR {e}")
            break

    out(f"  [CHANCE] detail URL 計{len(detail_ids)}件")

    # ── Step 2: 各detailページから情報抽出 ──
    for detail_path in detail_ids:
        detail_url = urljoin(_CHANCE_BASE, detail_path)
        if detail_path in processed_set:
            continue

        try:
            code, html, _ = fetch(detail_url)
            if code != 200:
                continue

            # jump.srv URL 抽出
            jump_match = re.search(
                r'(https://www\.chance\.com/jump\.srv\?id=\d+&s=[a-zA-Z0-9]+)', html
            )
            if not jump_match:
                out(f"  [CHANCE] jump.srv なし: {detail_path}")
                continue
            jump_url = jump_match.group(1)

            # jump.srv にアクセス → 302リダイレクト先のX URLを取得
            try:
                _, _, x_url = fetch(jump_url)
            except Exception as e:
                out(f"  [CHANCE] jump.srv リダイレクト失敗: {detail_path} - {e}")
                continue

            if not x_url or not re.search(r'https?://(?:x|twitter)\.com/', x_url):
                continue

            # /status/ が含まれていないX URLはスキップ（アカウントページ）
            if '/status/' not in x_url:
                continue

            if x_url in seen_x_urls or x_url in processed_set:
                continue
            seen_x_urls.add(x_url)

            # 締切日抽出: <dt>応募締切</dt><dd>M/D</dd>
            deadline = ""
            dm = re.search(r'<dt>応募締切</dt><dd>(\d{1,2})/(\d{1,2})', html)
            if dm:
                month = int(dm.group(1))
                day = int(dm.group(2))
                deadline = f"2026-{month:02d}-{day:02d}"

            # 当選者数抽出: <dt>当選者数</dt><dd><span>N名様</span>
            winner_count = 0
            wm = re.search(
                r'<dt>当選者数</dt><dd><span>(\d[\d,]*)名様</span>', html
            )
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

        time.sleep(0.3)  # 負荷軽減

    out(f"  [CHANCE] 計{len(items)}件")
    return items
