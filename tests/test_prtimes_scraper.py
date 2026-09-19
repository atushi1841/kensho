"""tests/test_prtimes_scraper.py — PR TIMES スクレイパのユニットテスト (第9弾 / 収集源第5ソース).

_fetch_with_retry をモックしてネットワークへ依存しない。
対象 (t_a9c1b208, 2026-09-19): PR TIMES プレスリリースの記念プレゼント・抽選キャンペーンを
収集源に追加。リリース本文に埋め込まれた X `/status/<id>` ツイートのみを収集し、
プロフィール(x.com/company) へのリンクだけのリリースは除外することを検証する。
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kensho.scraping.sources import prtimes  # noqa: E402


class _Log:
    """out コールバック代わりの簡易コレクタ。"""

    def __init__(self) -> None:
        self.buf = io.StringIO()

    def __call__(self, msg: str) -> None:
        self.buf.write(str(msg) + "\n")


def _kw_page_html(*pairs: tuple[str, str]) -> str:
    links = "".join(f'<a href="{u}" title="{t}">x</a>' for u, t in pairs)
    return f"<html><body>{links}</body></html>"


def _release_html(status_url: str = "", body: str = "") -> str:
    parts = ["<html><body>", '<a href="https://x.com/company">公式X</a>']
    if status_url:
        parts.append(f'<a href="{status_url}">応募</a>')
    parts.append(body)
    parts.append("</body></html>")
    return "".join(parts)


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, responses: dict[str, tuple[int, str]]) -> None:
    def fake_fetch(url: str, **_: Any) -> tuple[int, str, str]:
        code, html = responses.get(url, (404, ""))
        return code, html, url

    monkeypatch.setattr(prtimes, "_fetch_with_retry", fake_fetch)


@pytest.fixture()
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prtimes.time, "sleep", lambda _s: None)


def _page_responses(release_url: str, title: str) -> dict[str, tuple[int, str]]:
    return {
        prtimes._kw_page_url("プレゼント"): (200, _kw_page_html((release_url.replace("https://prtimes.jp", ""), title))),
        prtimes._kw_page_url("キャンペーン"): (200, "<html></html>"),
        prtimes._kw_page_url("抽選"): (200, "<html></html>"),
        prtimes._kw_page_url("新商品"): (200, "<html></html>"),
    }


def test_extracts_embedded_x_status_url(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    """本文に X /status/ URL を埋め込んだリリースを収集する（メインケース）。"""
    release_url = "https://prtimes.jp/main/html/rd/p/000000011.000115947.html"
    resp = _page_responses(release_url, "絵本プレゼントキャンペーン")
    resp[release_url] = (
        200,
        _release_html(
            status_url="https://x.com/LINEGIFT_JP/status/2096720170106667370",
            body="<p>応募締切：2026年9月30日（水）23:59 抽選で5名様にプレゼント</p>",
        ),
    )
    _patch_fetch(monkeypatch, resp)

    items = prtimes.scrape_prtimes(_Log(), set(), ["atushi16"])

    assert len(items) == 1
    it = items[0]
    assert it["x_url"] == "https://x.com/LINEGIFT_JP/status/2096720170106667370"
    assert it["source"] == "prtimes"
    assert it["deadline"] == "2026-09-30"
    assert it["winner_count"] == 5
    assert it["tweet_id"] == "2096720170106667370"
    assert set(it["applied"].keys()) == {"atushi16"}


def test_skips_profile_only_release(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    """X プロフィールリンクのみ（/status/ 無し）のリリースは収集しない。"""
    release_url = "https://prtimes.jp/main/html/rd/p/000000023.000141863.html"
    resp = _page_responses(release_url, "新商品発表")
    resp[release_url] = (200, _release_html())  # プロフィール x.com/company のみ
    _patch_fetch(monkeypatch, resp)

    items = prtimes.scrape_prtimes(_Log(), set(), ["atushi16"])

    assert items == []


def test_processed_release_skipped(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    """processed_set 済みのリリースURLは再取得しない。"""
    release_url = "https://prtimes.jp/main/html/rd/p/000000032.000184472.html"
    _patch_fetch(monkeypatch, _page_responses(release_url, "キャンペーン"))

    items = prtimes.scrape_prtimes(_Log(), {release_url}, ["atushi16"])

    assert items == []


def test_deadline_requires_anchor(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    """締切アンカー（締切/…まで/応募期間）直後に日付が無ければ deadline は空（og:release誤検知防止）。"""
    release_url = "https://prtimes.jp/main/html/rd/p/000000282.000110808.html"
    resp = _page_responses(release_url, "リリース")
    resp[release_url] = (
        200,
        "<html><body>"
        '<meta name="og:release" content="2026年9月19日">'
        "本日2026年9月19日、新商品を発売しました。"
        "(応募締切:フォロー&amp;RTで応募完了)"
        '<a href="https://x.com/foo/status/777">応募</a>'
        "</body></html>",
    )
    _patch_fetch(monkeypatch, resp)

    items = prtimes.scrape_prtimes(_Log(), set(), ["atushi16"])

    assert len(items) == 1
    # 「締切:」直後に日付が無い（フォロー&RTのみ）ため空 deadline → snowflake年齢パージへ委ねる
    assert items[0]["deadline"] == ""
