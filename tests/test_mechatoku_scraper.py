"""tests/test_mechatoku_scraper.py — mechatoku.com（めちゃ得ページ）スケレイパのユニットテスト."""
from __future__ import annotations
import io
import sys
from pathlib import Path
from typing import Any
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kensho.scraping.sources import mechatoku


class _Log:
    def __init__(self) -> None:
        self.buf = io.StringIO()
    def __call__(self, msg: str) -> None:
        self.buf.write(str(msg) + "\n")


def _html_listing(cid_links: list[str]) -> str:
    hrefs = "".join(f'<a href="https://www.mechatoku.com/ckensho/shousai/cid/{cid}">記事</a>' for cid in cid_links)
    return f"<html><body><table>{hrefs}</table></body></html>"


def _html_detail(x_url: str, deadline: str = "", winner: int = 0) -> str:
    dl = f"【最終応募締切】 {deadline}" if deadline else ""
    wc = f"【賞品】抽選で{winner}名様" if winner else ""
    og = f'<meta property="og:url" content="{x_url}">' if x_url else ""
    title = "テスト懸賞タイトル"
    return f"""<html><head><title>{title}:とらたぬ情報</title>{og}</head>
<body><h2>{title}</h2><p>{dl} {wc}</p></body></html>"""


def test_scrape_mechatoku_pagination_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        calls.append(url)
        if url == "https://www.mechatoku.com/ckensho/ichiran/":
            return 200, _html_listing(["/ckensho/shousai/cid/100", "/ckensho/shousai/cid/101", "/ckensho/shousai/cid/900", "/ckensho/shousai/cid/901", "/ckensho/shousai/cid/902"]), url
        if "/ckensho/ichiran/page/2" in url:
            return 200, _html_listing(["/ckensho/shousai/cid/101", "/ckensho/shousai/cid/102", "/ckensho/shousai/cid/900", "/ckensho/shousai/cid/901", "/ckensho/shousai/cid/902"]), url
        if "/ckensho/ichiran/page/3" in url:
            return 404, "", url
        if "/ckensho/shousai/cid/100" in url:
            return 200, _html_detail("https://x.com/a/status/111", "2026年9月15日", 10), url
        if "/ckensho/shousai/cid/101" in url:
            return 200, _html_detail("https://x.com/b/status/222", "2026年9月20日", 5), url
        if "/ckensho/shousai/cid/102" in url:
            return 200, _html_detail("https://x.com/c/status/333", "2026年10月1日", 20), url
        return 200, "<html></html>", url

    monkeypatch.setattr(mechatoku, "_fetch_with_retry", fake_fetch)
    # Override max pages
    original = mechatoku._MECHATOKU_MAX_PAGES
    mechatoku._MECHATOKU_MAX_PAGES = 3
    try:
        log = _Log()
        items = mechatoku.scrape_mechatoku(log, set(), ["atushi16"])
        urls = {it["x_url"] for it in items}
        assert urls == {
            "https://x.com/a/status/111",
            "https://x.com/b/status/222",
            "https://x.com/c/status/333",
        }
        assert len(items) == 3
        # cid/101 is in both page1 and page2 → deduped
        assert sum(1 for it in items if it["x_url"] == "https://x.com/b/status/222") == 1
    finally:
        mechatoku._MECHATOKU_MAX_PAGES = original


def test_scrape_mechatoku_deadline_and_winner(monkeypatch: pytest.MonkeyPatch) -> None:
    html = _html_detail("https://x.com/a/status/999", "2026年9月15日", 12)
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        if "/ichiran" in url:
            return 200, _html_listing(["/ckensho/shousai/cid/500"]), url
        return 200, html, url

    monkeypatch.setattr(mechatoku, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = mechatoku.scrape_mechatoku(log, set(), ["atushi16"])
    assert len(items) == 1
    it = items[0]
    assert it["deadline"] == "2026-09-15"
    assert it["winner_count"] == 12
    assert it["source"] == "mechatoku"
    assert it["detail_url"] == "/mechatoku/shousai/cid/500"
    assert set(it["applied"].keys()) == {"atushi16"}


def test_scrape_mechatoku_process_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    html = _html_detail("https://x.com/a/status/111", "2026年9月15日", 5)
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        return 200, html, url

    monkeypatch.setattr(mechatoku, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = mechatoku.scrape_mechatoku(log, {"https://x.com/a/status/111"}, ["atushi16"])
    assert items == []


def test_scrape_mechatoku_no_x_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """X URLなしの詳細ページはスキップされる。"""
    html_no_x = "<html><body><h2>タイトル</h2></body></html>"
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        if "/ichiran/" in url:
            return 200, _html_listing(["/ckensho/shousai/cid/200"]), url
        return 200, html_no_x, url

    monkeypatch.setattr(mechatoku, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = mechatoku.scrape_mechatoku(log, set(), ["atushi16"])
    assert items == []
