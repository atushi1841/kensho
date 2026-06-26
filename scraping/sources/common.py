"""共通ユーティリティ — 全収集源で使う関数・定数"""
from __future__ import annotations

import httpx
import json
import re
import time
import random as _random
from datetime import datetime
from pathlib import Path
from typing import Any

# ── ベースURL ──
BASE_URL: str = "https://www.knshow.com"
KENKAKU_BASE: str = "https://www.ken-kaku.com/cgi-bin/present/"

# ── User-Agent ローテーション（BOT検出回避）──
_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]
_UA_INDEX: int = _random.randint(0, len(_USER_AGENTS) - 1)

HEADERS: dict[str, str] = {
    "User-Agent": _USER_AGENTS[_UA_INDEX],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}


# ── 指数バックオフリトライ ──
def _fetch_with_retry(
    url: str, referer: str | None = None, max_retries: int = 3, timeout: int = 15
) -> tuple[int, str, str]:
    """
    HTTP GET with exponential backoff.
    HTTP 5xx / タイムアウト / ネットワークエラー時にリトライ。
    """
    for attempt in range(max_retries):
        try:
            code, html, final_url = fetch(url, referer=referer, timeout=timeout)
            if code < 500:
                return code, html, final_url
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError):
            pass
        except Exception as e:
            break
        if attempt < max_retries - 1:
            delay: float = (2**attempt) + _random.uniform(0, 1)
            time.sleep(delay)
    code, html, final_url = 0, "", ""
    try:
        code, html, final_url = fetch(url, referer=referer, timeout=timeout)
    except Exception:
        pass
    return code, html, final_url


def load_json(path: Path, default: Any = None) -> Any:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default if default is not None else {}


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch(
    url: str, referer: str | None = None, timeout: int = 15
) -> tuple[int, str, str]:
    h: dict[str, str] = dict(HEADERS)
    if referer:
        h["Referer"] = referer
    with httpx.Client(follow_redirects=False, timeout=timeout) as c:
        r = c.get(url, headers=h)
        # 明示的エンコーディング: Content-Type→meta→UTF-8 の優先順位
        html: str = _decode_response(r)
        return r.status_code, html, str(r.url)


def _decode_response(r: httpx.Response) -> str:
    """HTTPレスポンスからHTMLを正しいエンコーディングでデコード。
    Content-Type ヘッダー → HTML meta charset → UTF-8 の優先順位。
    """
    # Content-Type の charset を使う (httpxが既に設定)
    if r.encoding and r.encoding.lower() not in ("utf-8", "ascii", "iso-8859-1"):
        try:
            return r.content.decode(r.encoding, errors="replace")
        except (LookupError, ValueError):
            pass
    # 生バイトから charset を検出
    raw: bytes = r.content
    # HTMLのmeta charset を検出
    m = re.search(
        rb'<meta[^>]+charset\s*=\s*["\']?([a-zA-Z0-9_\-]+)["\'\s/>]',
        raw[:4096],
        re.IGNORECASE,
    )
    if m:
        guessed: str = m.group(1).decode("ascii", errors="replace").lower()
        if guessed != "utf-8":
            try:
                return raw.decode(guessed, errors="replace")
            except (LookupError, ValueError):
                pass
    # 最終手段: UTF-8 (Web標準)
    return raw.decode("utf-8", errors="replace")


# ── 期限切れアイテムの自動パージ ──
_EXPIRY_DAYS: int = 30


# ── スキップキーワード（引用・コメント・視聴・画像・質問・アプリ等 — RP/リプライ/リポストは通常応募なので除外）──
_SKIP_KEYWORDS: list[str] = [
    "引用RT",
    "引用リツイート",
    "引用ツイート",
    "引用して",
    "引用＆",
    "引用&",
    "引用RT&",
    "引用",
    "コメントして",
    "コメント＆",
    "コメント&",
    "コメント",
    "#引用",
    "#コメント",
    "視聴",
    "画像",
    "チェック",
    "質問",
    "ページ",
    "アプリ",
]


def has_skip_keyword(text: str) -> bool:
    """テキストにスキップキーワード（引用・コメント応募）が含まれているか判定"""
    t: str = text.lower()
    for kw in _SKIP_KEYWORDS:
        if kw.lower() in t:
            return True
    return False


def _is_expired(deadline_str: str, now: datetime | None = None) -> bool:
    """締切日が _EXPIRY_DAYS 以上経過していれば True"""
    if not deadline_str:
        return False
    if now is None:
        now = datetime.now()
    try:
        dl: datetime = datetime.strptime(deadline_str, "%Y-%m-%d")
        return (now - dl).days > _EXPIRY_DAYS
    except (ValueError, TypeError):
        return False
