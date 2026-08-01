"""
Kensho Scrapling Fetcher — Cloudflare / Turnstile / Bot 検出回避フェッチャー

Scrapling 0.4+ を使用したHTTPフェッチ。
- TLS指紋偽装（curl_cffi）
- ブラウザフィンガープリント自動生成（browserforge）
- Cloudflare Turnstile / Challenge ページの自動突破
- アダプティブパーサー（サイト構造変化の追跡）
- プロキシ対応（SOCKS5含む）

インターフェースは common.py の fetch() / _fetch_with_retry() と互換。
"""

from __future__ import annotations

import random
import time
from typing import Any

from scrapling import Fetcher

# ── Scrapling Fetcher（シングルトン）──
_FETCHER: Fetcher | None = None


def _get_fetcher(save_on_disk: bool = False) -> Fetcher:
    """遅延初期化で Fetcher インスタンスを取得"""
    global _FETCHER
    if _FETCHER is None:
        _FETCHER = Fetcher()
    return _FETCHER


def scrapling_fetch(
    url: str,
    referer: str | None = None,
    timeout: int = 30,
    proxy: str | None = None,
) -> tuple[int, str, str]:
    """
    Scrapling Fetcher を使ってURLを取得。

    Args:
        url: 取得先URL
        referer: Refererヘッダー（指定なし → https://www.google.com/ が自動設定される）
        timeout: タイムアウト秒数（デフォルト30秒。Cloudflare突破に時間がかかる場合あり）
        proxy: プロキシURL（例: socks5h://172.26.80.1:1081）

    Returns:
        (status_code, html_text, final_url) — common.fetch() 互換
    """
    f = _get_fetcher()
    kwargs: dict[str, Any] = {"timeout": timeout}
    if referer:
        kwargs["referer"] = referer
    if proxy:
        kwargs["proxy"] = proxy

    resp = f.get(url, **kwargs)

    status = getattr(resp, "status", 0) or 0

    # Scrapling 0.4: .body は bytes、.text は CSSセレクタ用 TextHandler
    # 生HTMLが必要な場合は .body をデコード
    body = getattr(resp, "body", None)
    if isinstance(body, bytes):
        import chardet

        detected = chardet.detect(body)
        enc = detected.get("encoding", "utf-8") or "utf-8"
        html_str: str = body.decode(enc, errors="replace")
    else:
        html_str = str(getattr(resp, "text", "")) if getattr(resp, "text", None) else ""

    final_url = getattr(resp, "url", url) or url

    return status, html_str, final_url


def scrapling_fetch_with_retry(
    url: str,
    referer: str | None = None,
    max_retries: int = 3,
    timeout: int = 30,
    proxy: str | None = None,
) -> tuple[int, str, str]:
    """
    scrapling_fetch の指数バックオフリトライ版。
    common._fetch_with_retry() 互換。
    """
    for attempt in range(max_retries):
        try:
            code, html, final_url = scrapling_fetch(url, referer=referer, timeout=timeout, proxy=proxy)
            if code < 500:
                return code, html, final_url
        except Exception:
            pass
        if attempt < max_retries - 1:
            delay: float = (2**attempt) + random.uniform(0, 1)
            time.sleep(delay)
    # 最終リトライ
    code, html, final_url = 0, "", ""
    try:
        code, html, final_url = scrapling_fetch(url, referer=referer, timeout=timeout, proxy=proxy)
    except Exception:
        pass
    return code, html, final_url


def is_scrapling_available() -> bool:
    """Scrapling が正常に使えるか確認"""
    try:
        f = _get_fetcher()
        resp = f.get("https://httpbin.org/status/200", timeout=10)
        return getattr(resp, "status", 0) == 200
    except Exception:
        return False
