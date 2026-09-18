"""tests/test_kensho_everyday_retry.py — kensho-everyday RSS取得のリトライ強化テスト（t_350bc813）.

変更内容: RSSフィード取得を 裸の fetch() → common._fetch_with_retry(source="kensho-everyday") へ変更。
- ConnectTimeout/5xx時に指数バックオフでリトライし、完全dropを回避（リトライ本体は _fetch_with_retry 内）
- source_health へ成功/失敗を記録（継続監視）
ネットワーク・sleepは全てmock（tests/AGENTS.mdルール準拠）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from kensho.scraping.sources import common  # noqa: E402
from kensho.scraping.sources import kensho_everyday as kevery  # noqa: E402

_RSS: str = kevery._KENSHO_EVERY_RSS
_ARTICLE: str = "https://kensho-everyday.com/archives/12345"
_RSS_HTML: str = (
    "<rss><channel><title>X</title>"
    f"<link>https://kensho-everyday.com</link>"
    f"<item><link>{_ARTICLE}</link></item>"
    "</channel></rss>"
)
_ARTICLE_HTML: str = (
    '<html><body><a href="https://x.com/testuser/status/999">tweet</a>'
    "<p>締切 2026年10月5日 当選 3名様</p></body></html>"
)


class _Log:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, msg: str) -> None:
        self.lines.append(str(msg))


def _install_fetch(monkeypatch: Any, script: dict[str, list[Any]]) -> list[str]:
    """共通 fetch() を差し替え、例外/応答を URL 別にキューでスクリプト化。"""
    calls: list[str] = []

    def fake(url: str, **kwargs: Any) -> tuple[int, str, str]:
        calls.append(url)
        q = script.get(url)
        if q:
            nxt = q.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            if isinstance(nxt, tuple):
                code, html, fin = nxt
                return int(code), str(html), str(fin)
        return 200, _RSS_HTML if url == _RSS else _ARTICLE_HTML, url

    monkeypatch.setattr(common, "fetch", fake)
    return calls


def test_rss_retry_on_connect_timeout_then_success(monkeypatch: Any) -> None:
    """ConnectTimeout → _fetch_with_retry 内でリトライ → 次で成功 → 記事からX URL取得される（完全drop回避）。"""
    script: dict[str, list[Any]] = {
        _RSS: [httpx.ConnectTimeout("c"), (200, _RSS_HTML, _RSS)],
        _ARTICLE: [(200, _ARTICLE_HTML, _ARTICLE)],
    }
    calls = _install_fetch(monkeypatch, script)
    log = _Log()
    items = kevery.scrape_kensho_everyday(log, set(), ["atushi16"])

    assert calls.count(_RSS) == 2, f"RSSはConnectTimeout+リトライで計2回叩かれる: {calls}"
    assert len(items) == 1
    assert items[0]["x_url"] == "https://x.com/testuser/status/999"
    assert items[0]["source"] == "kensho-everyday"
    assert items[0]["winner_count"] == 3


def test_rss_non200_aborts_without_articles(monkeypatch: Any) -> None:
    """RSSがHTTP非200 → 記事処理せず終了。"""
    def fake(url: str, **kwargs: Any) -> tuple[int, str, str]:
        return (500, "", url) if url == _RSS else (200, _ARTICLE_HTML, url)

    monkeypatch.setattr(common, "fetch", fake)
    log = _Log()
    items = kevery.scrape_kensho_everyday(log, set(), ["atushi16"])
    assert items == []
    assert any("RSS: HTTP 500" in m for m in log.lines)


def test_rss_uses_source_health_source_name(monkeypatch: Any) -> None:
    """RSS取得が _fetch_with_retry(source="kensho-everyday") を呼ぶ＝ヘルス記録され継続監視される。"""
    seen_sources: list[str | None] = []
    real = common._fetch_with_retry

    def spy(url: str, **kwargs: Any) -> tuple[int, str, str]:
        seen_sources.append(kwargs.get("source"))
        return real(url, **kwargs)

    monkeypatch.setattr(kevery, "_fetch_with_retry", spy)
    monkeypatch.setattr(common, "fetch", lambda url, **kw: (200, _RSS_HTML, url))
    log = _Log()
    kevery.scrape_kensho_everyday(log, set(), ["atushi16"])
    assert "kensho-everyday" in seen_sources
