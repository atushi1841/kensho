"""twscrape — X API直接検索で懸賞ツイートを収集（asyncio利用）"""
from __future__ import annotations

import asyncio
import os
import json as _json
import re
from typing import Any

from twscrape import API, gather

from .common import has_skip_keyword

# ── 第6収集源: twscrape（X API直接検索）──
_TWSCRAPE_QUERIES: list[str] = [
    "懸賞 フォロー リポスト プレゼント lang:ja",
    "フォロー&RT プレゼント 抽選 lang:ja",
    "キャンペーン フォロー リポスト 当選 lang:ja",
    "RT プレゼント 抽選 100名 lang:ja",
    "フォロー リツイート プレゼント 懸賞 lang:ja",
]


def scrape_twscrape(
    out: Any,
    processed_set: set[str],
    account_keys: list[str],
    session_path: str | None = None,
) -> list[dict[str, Any]]:
    """twscrape を使ってXを直接検索し懸賞ツイートを収集。
    auth_token は session_path のJSON or config指定から取得。
    戻り値: collected.json 互換のアイテムリスト。
    """
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    # ── auth_token 読み込み ──
    auth_token: str = ""
    ct0: str = ""
    if session_path and os.path.exists(session_path):
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                session_data: dict[str, Any] = _json.load(f)
            cookies: dict[str, str] = {
                c["name"]: c["value"] for c in session_data.get("cookies", [])
            }
            auth_token = cookies.get("auth_token", "")
            ct0 = cookies.get("ct0", "")
        except Exception as e:
            out(f"  [TWSCRAPE] session読み込み失敗: {e}")

    if not auth_token:
        out("  [TWSCRAPE] auth_tokenなし - スキップ")
        return items

    async def _run() -> list[dict[str, Any]]:
        api = API()
        cookie_str: str = f"auth_token={auth_token}; ct0={ct0}"
        await api.pool.add_account_cookies("twscrape_bot", cookie_str)
        found: list[dict[str, Any]] = []

        for query in _TWSCRAPE_QUERIES:
            try:
                tweets = await gather(api.search(query, limit=10))
                for tw in tweets:
                    x_url: str = f"https://x.com/{tw.user.username}/status/{tw.id}"
                    if x_url in seen_x_urls:
                        continue
                    if x_url in processed_set:
                        continue
                    seen_x_urls.add(x_url)

                    # テキストから締切日を推定（ツイート内の日付）
                    deadline: str = ""
                    text: str = tw.rawContent or ""
                    dm = re.search(r"(\d{1,2})月(\d{1,2})日", text)
                    if dm:
                        deadline = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"

                    # 当選人数
                    winner_count: int = 0
                    wm = re.search(r"(\d[\d,]*)\s*名", text)
                    if wm:
                        try:
                            winner_count = int(wm.group(1).replace(",", ""))
                        except ValueError:
                            pass

                    applied: dict[str, None] = {k: None for k in account_keys}
                    found.append(
                        {
                            "detail_url": f"/twscrape/tweet/{tw.id}",
                            "x_url": x_url,
                            "source": "twscrape",
                            "time": 0.0,
                            "deadline": deadline,
                            "winner_count": winner_count,
                            "days_remaining": "",
                            "applied": applied,
                            "keyword_flag": has_skip_keyword(text),
                        }
                    )
                    out(f"    ✅ {x_url[:65]}...")
            except Exception as query_e:
                out(f'  [TWSCRAPE] クエリ "{query[:30]}": {type(query_e).__name__}')

            await asyncio.sleep(0.5)

        return found

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        items = loop.run_until_complete(_run())
        loop.close()
    except Exception as e:
        out(f"  [TWSCRAPE] ERROR: {type(e).__name__}: {e}")

    out(f"  [TWSCRAPE] 計{len(items)}件取得")
    return items
