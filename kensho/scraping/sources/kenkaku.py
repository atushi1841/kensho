"""ken-kaku.com（懸賞館）— X/Twitter懸賞セクションからX URLを直接取得"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from .common import HEADERS, KENKAKU_BASE, _decode_response, has_skip_keyword

# ── 第2収集源: ken-kaku.com（懸賞館）──
_KENKAKU_PAGE_IDS: list[str] = [
    "104510000",
    "1045100010",
    "1045100020",
    "1045100030",
    "1045100040",
    "1045100050",
    "1045100060",
]

# critic v144: ページ単位timeoutリトライ（ken-kaku.com側レイテンシjitter対策）
# critic対策: リトライは指数バックオフで実行
# t_350bc813: リトライ3→5回、バックオフ2/4→3/6/10s（10sキャップ） — ConnectTimeout完全drop回避
_KENKAKU_MAX_RETRIES: int = 5  # 失敗時に追加で最大5回まで再試行（合計6アテンプト）
_KENKAKU_RETRY_BACKOFF: float = 3.0  # 指数バックオフのベース秒（3.0 * 2**attempt、10sキャップ）
_KENKAKU_RETRY_BACKOFF_MAX: float = 10.0  # バックオフ上限（3,6,10,10,10…）
# t_1cae393c: ConnectTimeout短縮 + フェイルオーバー用10sタイムアウト
_KENKAKU_TIMEOUT: int = 10


def scrape_kenkaku(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """ken-kaku.com のX/Twitter懸賞セクションからX URLを直接取得。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    for pid in _KENKAKU_PAGE_IDS:
        url: str = f"{KENKAKU_BASE}present.cgi?id={pid}"
        # fetchのみリトライ対象（critic v144）。最終失敗時はそのページだけスキップ。
        # ★ t_442337b4: ネットワーク層ヘルスモニタへ成功/失敗を記録（提案2）
        from kensho.scraping.source_health import note_fetch

        r: httpx.Response | None = None
        for attempt in range(1 + _KENKAKU_MAX_RETRIES):
            try:
                with httpx.Client(follow_redirects=True, timeout=_KENKAKU_TIMEOUT) as c:
                    resp = c.get(url, headers=headers_jp)
                if resp.status_code != 200:
                    out(f"  [KENKAKU] ページ{pid}: HTTP {resp.status_code} - スキップ")
                    note_fetch("ken-kaku", False, f"http={resp.status_code}")
                    r = None
                else:
                    r = resp
                    note_fetch("ken-kaku", True)
                break
            except Exception as e:
                if attempt < _KENKAKU_MAX_RETRIES:
                    # 指数バックオフ（critic対策）: base 3.0s → 3,6,12... を10s上限でキャップ（3,6,10,10,10）
                    delay: float = min(_KENKAKU_RETRY_BACKOFF * (2**attempt), _KENKAKU_RETRY_BACKOFF_MAX)
                    out(
                        f"  [KENKAKU] ページ{pid}: {type(e).__name__}"
                        f" → リトライ{attempt + 1}/{_KENKAKU_MAX_RETRIES}（{delay:.0f}s待ち）"
                    )
                    time.sleep(delay)
                    continue
                out(f"  [KENKAKU] ページ{pid}: ERROR {type(e).__name__}: {e}")
                note_fetch("ken-kaku", False, type(e).__name__)
                r = None
                break
        if r is None:
            time.sleep(0.3)  # 失敗ページ後も優しい間隔を維持
            continue

        try:
            html: str = _decode_response(r)
            # X URL を直接抽出
            for m in re.finditer(r"href=\"(https?://x\.com/[a-zA-Z0-9_]+/status/[0-9]+)\"", html):
                x_url: str = m.group(1)
                if x_url in seen_x_urls:
                    continue
                seen_x_urls.add(x_url)
                if x_url in processed_set:
                    continue

                # 仮のdetail_url（present.cgiのURLを使用）
                detail_url: str = f"/kenkaku/present.cgi?id={pid}/{len(items)}"

                # 締切日をtimeタグ or テキストから取得
                deadline: str = ""
                context_start: int = max(0, m.start() - 1200)
                context: str = html[context_start : min(len(html), m.end() + 400)]
                # <time datetime="YYYY-MM-DD"> (既存)
                dm = re.search(r"time\s+datetime=\"(\d{4}-\d{1,2}-\d{1,2})\"", context)
                if dm:
                    deadline = dm.group(1)
                else:
                    # YYYY年M月D日
                    dm = re.search(r"(202\d)[年/](\d{1,2})[月/](\d{1,2})", context)
                    if dm:
                        deadline = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                    else:
                        # M月D日
                        dm = re.search(r"(\d{1,2})月(\d{1,2})日", context)
                        if dm:
                            deadline = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"

                applied: dict[str, None] = {k: None for k in account_keys}
                items.append({
                    "detail_url": detail_url,
                    "x_url": x_url,
                    "source": "ken-kaku",
                    "time": 0.0,
                    "deadline": deadline,
                    "winner_count": 0,
                    "days_remaining": "",
                    "keyword_flag": has_skip_keyword(context),
                    "applied": applied,
                })
                out(f"    ✅ {x_url[:65]}...")
            time.sleep(0.3)  # 優しめの間隔
        except Exception as e:
            out(f"  [KENKAKU] ページ{pid}: ERROR {type(e).__name__}: {e}")

    out(f"  [KENKAKU] 計{len(items)}件取得")
    return items
