"""
Tests for knshow Cloudflare failure classification + browser fallback (critic t_c0e0563d).

対象仕様:
- classify_knshow_failure: 502/520-524 系の CF origin 障害ページ → origin_outage /
  "Just a moment..." 等のボットチャレンジ → bot_challenge / 403,429,503 → bot_challenge /
  判定不能 → unknown
- fetch_knshow_listing: 200 なら kind=ok / origin_outage はブラウザを起動せず即 fail-open /
  bot_challenge のときだけ実ブラウザへフォールバックし、成功で kind=browser_ok・失敗で従来結果を維持
- collector 側: 失敗種別を source_health の last_error へ `http=502(origin_outage)` 形式で記録し、
  Telegram 警報本文で「CF origin 障害」か「ボットチャレンジ」かを切り分ける

ネットワーク・実ブラウザは全て mock（tests/AGENTS.md ルール準拠）。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping import collector
from kensho.scraping.sources import browser_fetch, knshow
from kensho.scraping.sources.common import BASE_URL

_LIST_URL: str = f"{BASE_URL}/twitter"
_CF_502_BODY: str = "<html><head><title>knshow.com | 502: Bad Gateway</title></head><body>error code: 502</body></html>"
_CF_CHALLENGE_BODY: str = (
    "<html><head><title>Just a moment...</title></head>"
    "<body>Performing security verification</body></html>"
)
_OK_BODY: str = '<html><body><a href="/detail/abc.html">x</a></body></html>'


class _Log:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, msg: str) -> None:
        self.lines.append(str(msg))


def _fetcher(code: int, body: str) -> Any:
    """常に (code, body, url) を返す fetcher。"""

    def _f(url: str) -> tuple[int, str, str]:
        return code, body, str(url)

    return _f


class _BrowserSpy:
    """ブラウザフォールバックの呼出回数と戻り値を制御する fake。"""

    def __init__(self, result: tuple[int, str] | None = None, exc: Exception | None = None) -> None:
        self.calls: list[str] = []
        self._result = result
        self._exc = exc

    def __call__(self, url: str) -> tuple[int, str] | None:
        self.calls.append(str(url))
        if self._exc is not None:
            raise self._exc
        return self._result


class TestClassify:
    def test_502_body_is_origin_outage(self) -> None:
        assert knshow.classify_knshow_failure(502, _CF_502_BODY) == knshow.CF_ORIGIN_OUTAGE

    def test_502_error_code_only(self) -> None:
        assert knshow.classify_knshow_failure(502, "error code: 502") == knshow.CF_ORIGIN_OUTAGE

    @pytest.mark.parametrize(
        "code,marker",
        [(520, "error code: 520"), (521, "521: Web Server Is Down"), (523, "523: Origin Is Unreachable")],
    )
    def test_cf_5xx_family_is_origin_outage(self, code: int, marker: str) -> None:
        assert knshow.classify_knshow_failure(code, marker) == knshow.CF_ORIGIN_OUTAGE

    def test_just_a_moment_is_bot_challenge(self) -> None:
        assert knshow.classify_knshow_failure(403, _CF_CHALLENGE_BODY) == knshow.CF_BOT_CHALLENGE

    def test_challenge_platform_marker(self) -> None:
        body: str = "<script src=/cdn-cgi/challenge-platform/x>"
        assert knshow.classify_knshow_failure(503, body) == knshow.CF_BOT_CHALLENGE

    @pytest.mark.parametrize("code", [403, 429, 503])
    def test_bare_status_without_body_is_bot_challenge(self, code: int) -> None:
        assert knshow.classify_knshow_failure(code, "") == knshow.CF_BOT_CHALLENGE

    def test_unknown_is_fail_open(self) -> None:
        assert knshow.classify_knshow_failure(404, "") == knshow.CF_UNKNOWN
        assert knshow.classify_knshow_failure(0, None) == knshow.CF_UNKNOWN

    def test_origin_marker_wins_over_challenge_marker(self) -> None:
        """CF の 502 ページは challenge-platform のスクリプトも含むため、origin 判定を優先する。"""
        mixed: str = "challenge-platform error code: 502"
        assert knshow.classify_knshow_failure(502, mixed) == knshow.CF_ORIGIN_OUTAGE


class TestFetchListingFallback:
    def test_success_returns_ok_without_browser(self) -> None:
        spy = _BrowserSpy((200, "never used"))
        code, html, _url, kind = knshow.fetch_knshow_listing(_fetcher(200, _OK_BODY), _LIST_URL, browser_fetcher=spy)
        assert (code, kind) == (200, knshow.KNSHOW_OK)
        assert spy.calls == [], "200 でブラウザを起動しない（無駄な headless 起動の回避）"

    def test_origin_outage_does_not_launch_browser(self) -> None:
        """502(origin 障害) は実ブラウザでも通らないため、ブラウザ起動せず即 fail-open。"""
        spy = _BrowserSpy((200, _OK_BODY))
        log = _Log()
        code, _html, _url, kind = knshow.fetch_knshow_listing(
            _fetcher(502, _CF_502_BODY), _LIST_URL, out=log, browser_fetcher=spy
        )
        assert (code, kind) == (502, knshow.CF_ORIGIN_OUTAGE)
        assert spy.calls == [], "origin 障害でブラウザを起動しない（高コストかつ無効）"
        assert not any("実ブラウザ" in m for m in log.lines), log.lines

    def test_bot_challenge_falls_back_to_browser(self) -> None:
        spy = _BrowserSpy((200, _OK_BODY))
        log = _Log()
        code, html, url, kind = knshow.fetch_knshow_listing(
            _fetcher(403, _CF_CHALLENGE_BODY), _LIST_URL, out=log, browser_fetcher=spy
        )
        assert (code, kind) == (200, knshow.BROWSER_OK)
        assert html == _OK_BODY
        assert spy.calls == [_LIST_URL]
        assert any("ボットチャレンジ" in m for m in log.lines), log.lines

    def test_browser_unavailable_is_fail_open(self) -> None:
        """patchright 不在/起動不能（None 返却）→ 従来 httpx 経路の失敗結果を維持し収集は止めない。"""
        spy = _BrowserSpy(None)
        log = _Log()
        code, _html, _url, kind = knshow.fetch_knshow_listing(
            _fetcher(403, _CF_CHALLENGE_BODY), _LIST_URL, out=log, browser_fetcher=spy
        )
        assert (code, kind) == (403, knshow.CF_BOT_CHALLENGE)
        assert spy.calls == [_LIST_URL]
        assert any("fail-open" in m for m in log.lines), log.lines

    def test_browser_exception_is_fail_open(self) -> None:
        spy = _BrowserSpy(exc=RuntimeError("chromium launch failed"))
        code, _html, _url, kind = knshow.fetch_knshow_listing(
            _fetcher(403, _CF_CHALLENGE_BODY), _LIST_URL, browser_fetcher=spy
        )
        assert (code, kind) == (403, knshow.CF_BOT_CHALLENGE), "例外は握り潰し従来結果を維持"

    def test_browser_non_200_is_fail_open(self) -> None:
        spy = _BrowserSpy((502, _CF_502_BODY))
        code, _html, _url, kind = knshow.fetch_knshow_listing(
            _fetcher(403, _CF_CHALLENGE_BODY), _LIST_URL, browser_fetcher=spy
        )
        assert (code, kind) == (403, knshow.CF_BOT_CHALLENGE)

    def test_default_browser_fetcher_is_browser_fetch_module(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """browser_fetcher 未指定時は browser_fetch.fetch_via_browser が使われる（配線の実測）。"""
        calls: list[str] = []

        def _fake(url: str) -> tuple[int, str] | None:
            calls.append(str(url))
            return 200, _OK_BODY

        monkeypatch.setattr(knshow, "fetch_via_browser", _fake)
        code, _html, _url, kind = knshow.fetch_knshow_listing(_fetcher(403, _CF_CHALLENGE_BODY), _LIST_URL)
        assert (code, kind) == (200, knshow.BROWSER_OK)
        assert calls == [_LIST_URL]


class TestBrowserFetchModule:
    """browser_fetch.fetch_via_browser の fail-open（patchright 不在・例外時に None）。"""

    def test_returns_none_when_patchright_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "patchright", None)
        monkeypatch.setitem(sys.modules, "patchright.sync_api", None)
        assert browser_fetch.fetch_via_browser(_LIST_URL) is None

    def test_returns_none_when_launch_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = types.ModuleType("patchright.sync_api")

        def _boom() -> Any:
            raise RuntimeError("browser launch failed")

        setattr(mod, "sync_playwright", _boom)
        monkeypatch.setitem(sys.modules, "patchright.sync_api", mod)
        assert browser_fetch.fetch_via_browser(_LIST_URL) is None


class TestCollectorWiring:
    """collector 側の source_health ラベル / Telegram 警報本文（切り分け文言）。"""

    def test_error_label_carries_kind(self) -> None:
        assert collector._knshow_error_label(502, knshow.CF_ORIGIN_OUTAGE) == "http=502(origin_outage)"
        assert collector._knshow_error_label(403, knshow.CF_BOT_CHALLENGE) == "http=403(bot_challenge)"

    def test_error_label_backward_compatible(self) -> None:
        assert collector._knshow_error_label(502, knshow.CF_UNKNOWN) == "http=502"
        assert collector._knshow_error_label(0, knshow.CF_UNKNOWN) == "network"

    def test_cf_hint_distinguishes_origin_outage(self) -> None:
        hint = collector._knshow_cf_hint(knshow.CF_ORIGIN_OUTAGE)
        assert "origin 障害" in hint
        assert "実ブラウザでも不通" in hint

    def test_cf_hint_distinguishes_bot_challenge(self) -> None:
        hint = collector._knshow_cf_hint(knshow.CF_BOT_CHALLENGE)
        assert "ボットチャレンジ" in hint
        assert "origin 障害" not in hint

    def test_step1_uses_classified_listing_fetch(self) -> None:
        """Step1 一覧取得が分類付き fetch_knshow_listing を経由していること（配線の回帰ガード）。"""
        src: str = Path(collector.__file__).read_text(encoding="utf-8")
        # ★ t_4624904b: 完全一致から部分一致へ。実装は browser_fetcher=fetch_via_browser を
        #   追加で受け取るため、呼出先の前方一致で十分（将来のコード引数追加に追従しない硬いガード）。
        assert "fetch_knshow_listing(_do_fetch, url, out=out" in src
        assert "note_fetch(\"knshow\", False, _knshow_error_label(code, _kind))" in src
        assert "_knshow_cf_hint(_kind)" in src
