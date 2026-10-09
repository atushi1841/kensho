"""tests/test_appare_scraper.py — appare.com（懸賞天晴）スケレイパのユニットテスト."""
from __future__ import annotations
import io
import sys
from pathlib import Path
from typing import Any
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kensho.scraping.sources import appare


class _Log:
    def __init__(self) -> None:
        self.buf = io.StringIO()
    def __call__(self, msg: str) -> None:
        self.buf.write(str(msg) + "\n")


def _html_listing() -> str:
    links = "".join(
        f'<a href="search-category.cgi?links={i}">賞品{i}</a>'
        for i in range(340552, 340542, -1)
    )
    return f"""<HTML><BODY>
<table>{links}</table>
<p>全10件を表示</p>
</BODY></HTML>"""


def _html_detail(x_url: str, title: str = "テスト賞品", winner: int = 0) -> str:
    og = f'<meta property="og:url" content="{x_url}">' if x_url else ""
    wc = f"抽選で{winner}名様" if winner else ""
    return f"""<HTML><BODY>
<small>ID:340552</small><br><small>賞品:<small><b><font size=4><a href="search-category.cgi?links=340552" target="_blank">{title}</a></font></b></small>
{og}
<p>{wc}</p>
</BODY></HTML>"""


def test_scrape_appare_pagination_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        calls.append(url)
        if "mode=1new&page=1" in url or ("mode=1new" in url and "page" not in url):
            return 200, _html_listing(), url
        if "mode=1new&page=2" in url:
            return 200, _html_listing(), url
        if "mode=1new&page=3" in url:
            return 404, "", url
        if "links=340552" in url:
            return 200, _html_detail("https://x.com/a/status/111", "LG Styler", 777), url
        if "links=340551" in url:
            return 200, _html_detail("https://x.com/b/status/222", "Gift Card", 100), url
        if "links=340550" in url:
            return 200, _html_detail("https://x.com/c/status/333", "Travel Voucher", 50), url
        return 200, _html_detail("", "No X URL", 0), url

    monkeypatch.setattr(appare, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = appare.scrape_appare(log, set(), ["atushi16"])
    urls = {it["x_url"] for it in items}
    assert urls == {
        "https://x.com/a/status/111",
        "https://x.com/b/status/222",
        "https://x.com/c/status/333",
    }
    assert len(items) == 3
    assert sum(1 for it in items if it["x_url"] == "https://x.com/b/status/222") == 1


def test_scrape_appare_deadline_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    # 実サイトは href="..." のダブルクォート形式（2026-10-09実測）
    listing = '<p>締切: 10/17</p><a href="search-category.cgi?links=340552">商品</a>'
    detail = _html_detail("https://x.com/a/status/999", "抽選10名", 10)
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        if "mode=1new" in url:
            return 200, listing, url
        return 200, detail, url

    monkeypatch.setattr(appare, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = appare.scrape_appare(log, set(), ["atushi16"])
    assert len(items) == 1
    it = items[0]
    assert it["deadline"] == "2026-10-17"
    assert it["winner_count"] == 10
    assert it["source"] == "appare"
    assert set(it["applied"].keys()) == {"atushi16"}


def test_scrape_appare_process_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    listing = '<a href="search-category.cgi?links=340552">商品</a>'
    detail = _html_detail("https://x.com/a/status/111", "テスト", 5)
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        if "mode=1new" in url:
            return 200, listing, url
        return 200, detail, url

    monkeypatch.setattr(appare, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = appare.scrape_appare(log, {"https://x.com/a/status/111"}, ["atushi16"])
    assert items == []


def test_scrape_appare_no_x_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """X URLなしの詳細ページはスキップされる。"""
    listing = '<a href="search-category.cgi?links=340552">商品</a>'
    detail_no_x = "<HTML><BODY><p>賞品情報</p></BODY></HTML>"
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        if "mode=1new" in url:
            return 200, listing, url
        return 200, detail_no_x, url

    monkeypatch.setattr(appare, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = appare.scrape_appare(log, set(), ["atushi16"])
    assert items == []


def test_scrape_appare_redirect_final_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """詳細リンクがXへ直接リダイレクトする場合、final_urlからX URLを拾う（2026-10-09実測挙動）。"""
    listing = '<a href="search-category.cgi?links=340552">商品</a>'
    # 実サイト同様に本文へX URLを含まない
    detail_no_x = "<HTML><BODY><p>賞品情報</p></BODY></HTML>"
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        if "mode=1new" in url:
            return 200, listing, url
        return 200, detail_no_x, "https://x.com/lg_jpn/status/2097000000000000000"

    monkeypatch.setattr(appare, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = appare.scrape_appare(log, set(), ["atushi16"])
    assert len(items) == 1
    assert items[0]["x_url"] == "https://x.com/lg_jpn/status/2097000000000000000"
    assert items[0]["source"] == "appare"


def test_scrape_appare_302_meta_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """詳細ページは302を返しbodyのmeta refreshにX URLを含む（2026-10-09実測挙動）。"""
    listing = '<a href="search-category.cgi?links=340552">商品</a>'
    body_302 = '<meta http-equiv="refresh" content="0;url=https://x.com/lg_jpn/status/2107667234596528417">'
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        if "mode=1new" in url:
            return 200, listing, url
        return 302, body_302, url

    monkeypatch.setattr(appare, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = appare.scrape_appare(log, set(), ["atushi16"])
    assert len(items) == 1
    assert items[0]["x_url"] == "https://x.com/lg_jpn/status/2107667234596528417"
