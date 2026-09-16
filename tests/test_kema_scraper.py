"""tests/test_kema_scraper.py — ke-ma.net（第5収集源）スケレイパのユニットテスト.

fetch() をモックしてネットワークへ依存しない。
収集パイプラインのみの変更（応募ロジック非変更）。
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kensho.scraping.sources import kema  # noqa: E402


class _Log:
    """out コールバック代わりの簡易コレクタ。"""

    def __init__(self) -> None:
        self.buf = io.StringIO()

    def __call__(self, msg: str) -> None:
        self.buf.write(str(msg) + "\n")


def _html_page(urls: list[str], offset: int = 1200) -> str:
    """X URL を + 締切日・当選人数の文脈付きで含む HTML を生成。
    offset は文中の X URL 位置（deadline 抽出に使う ctx に含まれるよう十分大きく）。
    """
    prefix: str = "　" * offset if offset else ""
    blocks: list[str] = []
    for i, u in enumerate(urls):
        dl: str = f"2026年9月{20 - i}日" if i % 3 != 2 else f"{12 - i}月5日"
        ctx: str = f"{prefix}<p>応募締切 {dl} 当選 {5 + i}名 様</p>"
        blocks.append(ctx + f'<a href="{u}">ツイート</a>')
    return "<html><body>" + "".join(blocks) + "</body></html>"


def test_scrape_kema_pagination_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    """複数ページを巡回し、同一 X URL は重複しない。"""

    page1: str = _html_page(["https://x.com/a/status/111", "https://x.com/b/status/222", "https://x.com/c/status/333"])
    page2: str = _html_page(["https://x.com/c/status/333", "https://x.com/d/status/444"])  # c は page1 で既出

    calls: list[str] = []

    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        calls.append(url)
        if url.endswith("/open/"):
            return 200, page1, url
        if url.endswith("/open/page/2/"):
            return 200, page2, url
        if url.endswith("/open/page/3/"):
            return 404, "", url
        return 200, "<html></html>", url

    monkeypatch.setattr(kema, "_fetch_with_retry", fake_fetch)

    log = _Log()
    items = kema.scrape_kema(log, set(), ["atushi16"])

    urls = {it["x_url"] for it in items}
    assert urls == {
        "https://x.com/a/status/111",
        "https://x.com/b/status/222",
        "https://x.com/c/status/333",
        "https://x.com/d/status/444",
    }
    assert len(items) == 4
    # ページ2 の c は既出のため重複しない
    assert sum(1 for it in items if it["x_url"] == "https://x.com/c/status/333") == 1
    # ページ1→2→3(404) と巡回
    assert "/open/" in calls[0]
    assert "/open/page/2/" in calls[1]
    assert "/open/page/3/" in calls[2]


def test_scrape_kema_deadline_and_winner(monkeypatch: pytest.MonkeyPatch) -> None:
    """締切日 YYYY年M月D日 と当選人数を抽出する。"""
    html: str = '<p>応募締切 2026年9月15日 当選 12名 様</p><a href="https://x.com/a/status/999">ツイート</a>'

    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        return 200, html, url

    monkeypatch.setattr(kema, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = kema.scrape_kema(log, set(), ["atushi16"])

    assert len(items) == 1
    it = items[0]
    assert it["deadline"] == "2026-09-15"
    assert it["winner_count"] == 12
    assert it["source"] == "kema"
    assert it["detail_url"] == "/kema/open/0"
    assert set(it["applied"].keys()) == {"atushi16"}


def test_scrape_kema_process_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """processed_set 内の X URL はスキップされる。"""
    html: str = '<p>応募締切 9月15日</p><a href="https://x.com/a/status/111">ツイート</a>'

    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        return 200, html, url

    monkeypatch.setattr(kema, "_fetch_with_retry", fake_fetch)
    log = _Log()
    items = kema.scrape_kema(log, {"https://x.com/a/status/111"}, ["atushi16"])

    assert items == []
