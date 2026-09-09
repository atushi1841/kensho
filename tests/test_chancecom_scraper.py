"""tests/test_chancecom_scraper.py — chance.com スクレイパのユニットテスト.

_fetch_with_retry / _resolve_x_url をモックしてネットワークへ依存しない。
リグレッション対象 (t_5ed34bc3, 2026-09-09): サイト側が jump.srv の &s= トークンを
廃止したため strict マッチの正規表現が全滅し、収集連続0件になった。
新旧両形式の jump.srv URL を拾えることを検証する。
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kensho.scraping.sources import chancecom  # noqa: E402


class _Log:
    """out コールバック代わりの簡易コレクタ。"""

    def __init__(self) -> None:
        self.buf = io.StringIO()

    def __call__(self, msg: str) -> None:
        self.buf.write(str(msg) + "\n")


_LIST_HTML = (
    "<html><body>"
    '<a href="https://www.chance.com/present/detail/718697/">x</a>'
    '<a href="https://www.chance.com/present/detail/718698/">x</a>'
    "</body></html>"
)


def _detail_html(jump: str) -> str:
    return (
        "<html><body>"
        f'<a href="{jump}" rel="nofollow">賞品</a>'
        "<dl><dt>応募締切</dt><dd>9/20</dd>"
        "<dt>当選者数</dt><dd><span>5名様</span></dd></dl>"
        "</body></html>"
    )


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, responses: dict[str, tuple[int, str]]) -> None:
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        code, html = responses.get(url, (404, ""))
        return code, html, url

    monkeypatch.setattr(chancecom, "_fetch_with_retry", fake_fetch)


@pytest.fixture()
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chancecom.time, "sleep", lambda _s: None)


def test_new_format_jump_without_s_token(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    """2026-09 以降の新形式（&s= なし）でも収集できる — デッドソース再現テスト。"""
    _patch_fetch(
        monkeypatch,
        {
            chancecom._LIST_URL: (200, _LIST_HTML),
            "https://www.chance.com/present/detail/718697/": (
                200,
                _detail_html("https://www.chance.com/jump.srv?id=718697"),
            ),
            "https://www.chance.com/present/detail/718698/": (
                200,
                _detail_html("https://www.chance.com/jump.srv?id=718698"),
            ),
        },
    )
    monkeypatch.setattr(
        chancecom,
        "_resolve_x_url",
        lambda jump: "https://x.com/foo/status/123" if "718697" in jump else None,
    )

    items = chancecom.scrape_chancecom(_Log(), set(), ["atushi16"])

    assert len(items) == 1
    it = items[0]
    assert it["x_url"] == "https://x.com/foo/status/123"
    assert it["source"] == "chancecom"
    assert it["deadline"] == "2026-09-20"
    assert it["winner_count"] == 5
    assert it["detail_url"] == "/present/detail/718697/"
    assert set(it["applied"].keys()) == {"atushi16"}


def test_old_format_jump_with_s_token_still_works(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    """旧形式（&s= あり）の後方互換を維持する。"""
    _patch_fetch(
        monkeypatch,
        {
            chancecom._LIST_URL: (200, _LIST_HTML),
            "https://www.chance.com/present/detail/718697/": (
                200,
                _detail_html("https://www.chance.com/jump.srv?id=718697&s=abc123XY"),
            ),
        },
    )
    captured: list[str] = []

    def fake_resolve(jump: str) -> str | None:
        captured.append(jump)
        return "https://x.com/bar/status/456"

    monkeypatch.setattr(chancecom, "_resolve_x_url", fake_resolve)

    items = chancecom.scrape_chancecom(_Log(), set(), ["atushi16"])

    assert len(items) == 1
    assert captured == ["https://www.chance.com/jump.srv?id=718697&s=abc123XY"]


def test_processed_detail_path_skipped(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    """processed_set 済みの detail パスは再取得しない。"""
    _patch_fetch(
        monkeypatch,
        {
            chancecom._LIST_URL: (200, _LIST_HTML),
            "https://www.chance.com/present/detail/718697/": (
                200,
                _detail_html("https://www.chance.com/jump.srv?id=718697"),
            ),
        },
    )
    monkeypatch.setattr(chancecom, "_resolve_x_url", lambda _jump: "https://x.com/foo/status/123")

    items = chancecom.scrape_chancecom(_Log(), {"/present/detail/718697/"}, ["atushi16"])

    assert items == []
