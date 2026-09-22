"""
Tests for kensho/scraping/sources/knshow.py — critic t_18ecf0a5 knshow 502部分劣化対策
（kenkaku v144ページ単位リトライの移植・3アテンプト・10sキャップ）。

対象仕様:
- _KNSHOW_MAX_TRIES=3（合計3アテンプト = 初期 + リトライ2回）/ _KNSHOW_RETRY_BACKOFF=3.0
  （指数バックオフ: 3,6 → 10sキャップ）
- fetch_listing_with_retry: HTTP 5xx(502含む)/ネットワーク例外のみリトライ。非5xx(404等)は即スキップ
- resolve_redirect: ネットワーク例外のみ指数バックオフリトライ（最終失敗で再raise=呼出側がitem skip）
ネットワーク・sleepは全てmock（tests/AGENTS.mdルール準拠）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.sources import knshow
from kensho.scraping.sources.common import BASE_URL

_BASE: str = BASE_URL
_LIST_URL: str = f"{_BASE}/twitter"
_FINAL_URL: str = "https://x.com/testuser/status/1234567890123"


def _resp(code: int) -> tuple[int, str, str]:
    html = f"<html><body>status {code}</body></html>" if code == 200 else ""
    return code, html, _LIST_URL


def _script_fetcher(calls: list[str], script: list[Any]) -> Callable[..., tuple[int, str, str]]:
    """呼び出しごとに script を順に返す fetcher。末尾は 200 で固定。"""

    def _f(url: str) -> tuple[int, str, str]:
        calls.append(str(url))
        if script:
            nxt = script.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            code, html, fin = nxt
            return int(code), str(html), str(fin)
        return 200, "<html><body>ok</body></html>", str(url)

    return _f


@pytest.fixture()
def sleep_spy(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr("kensho.scraping.sources.knshow.time.sleep", lambda s: recorded.append(float(s)))
    return recorded


class _Log:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, msg: str) -> None:
        self.lines.append(str(msg))


class TestRetryConstants:
    """knshow.py のリトライ定数（t_18ecf0a5 / 3アテンプト・10sキャップ）との整合アサーション"""

    def test_max_tries_is_3(self) -> None:
        assert knshow._KNSHOW_MAX_TRIES == 3

    def test_backoff_is_3_seconds(self) -> None:
        assert knshow._KNSHOW_RETRY_BACKOFF == 3.0

    def test_backoff_max_is_10_seconds(self) -> None:
        assert knshow._KNSHOW_RETRY_BACKOFF_MAX == 10.0


class TestListingRetry:
    """fetch_listing_with_retry: 502/ネットワーク例外を3アテンプトまで指数バックオフでリトライ"""

    def test_502_then_success(self, sleep_spy: list[float]) -> None:
        calls: list[str] = []
        script = [_resp(502), _resp(200)]
        code, html, _ = knshow.fetch_listing_with_retry(_script_fetcher(calls, script), _LIST_URL)
        assert code == 200
        assert calls == [_LIST_URL, _LIST_URL], "502→リトライ→200"
        # base 3.0 * 2**0 = 3.0（1回目リトライ待機）
        assert sleep_spy == [3.0], f"バックオフ(3.0s): {sleep_spy}"

    def test_two_502_then_success(self, sleep_spy: list[float]) -> None:
        calls: list[str] = []
        script = [_resp(502), _resp(502), _resp(200)]
        code, html, _ = knshow.fetch_listing_with_retry(_script_fetcher(calls, script), _LIST_URL)
        assert code == 200
        assert calls == [_LIST_URL] * 3
        # バックオフ 3.0 * 2**0 = 3.0 / 3.0 * 2**1 = 6.0
        assert sleep_spy == [3.0, 6.0], f"バックオフ(3,6): {sleep_spy}"

    def test_all_502_gives_up_finitely(self, sleep_spy: list[float]) -> None:
        calls: list[str] = []
        script = [_resp(502), _resp(502), _resp(502)]
        code, html, _ = knshow.fetch_listing_with_retry(_script_fetcher(calls, script), _LIST_URL)
        assert code == 502, "最終コード502が返る（呼出側で成功/失敗判定）"
        assert calls == [_LIST_URL] * 3, "3アテンプトで打ち切り・無限リトライ禁止"
        assert sleep_spy == [3.0, 6.0]

    def test_non500_not_retried(self, sleep_spy: list[float]) -> None:
        calls: list[str] = []
        script = [_resp(404)]
        code, html, _ = knshow.fetch_listing_with_retry(_script_fetcher(calls, script), _LIST_URL)
        assert code == 404
        assert calls == [_LIST_URL], "404等の非5xxは即スキップ（リトライ不発火）"
        assert sleep_spy == []

    def test_network_exception_then_success(self, sleep_spy: list[float]) -> None:
        calls: list[str] = []
        script = [httpx.ConnectTimeout("boom"), _resp(200)]
        code, html, _ = knshow.fetch_listing_with_retry(_script_fetcher(calls, script), _LIST_URL)
        assert code == 200
        assert calls == [_LIST_URL] * 2
        assert sleep_spy == [3.0]

    def test_emits_retry_log(self, sleep_spy: list[float]) -> None:
        log = _Log()
        script = [_resp(502), _resp(200)]
        knshow.fetch_listing_with_retry(_script_fetcher([], script), _LIST_URL, out=log)
        assert any("リトライ1/2" in m for m in log.lines), log.lines
        assert any("HTTP 502" in m for m in log.lines), log.lines


# ── resolve_redirect リトライ ──
class _FakeResp:
    def __init__(self, url: str) -> None:
        self.url = url


class _FakeClient:
    def __init__(self, engine: Callable[[], Any]) -> None:
        self._engine = engine

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def get(self, url: str, headers: dict[str, str] | None = None) -> Any:
        nxt = self._engine()
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


class TestResolveRedirectRetry:
    @pytest.fixture()
    def client_factory(self, monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable[[], Any]], _FakeClient]:
        def install(engine: Callable[[], Any]) -> _FakeClient:
            client = _FakeClient(engine)
            monkeypatch.setattr("kensho.scraping.sources.knshow.httpx.Client", lambda *a, **k: client)
            return client

        return install

    def test_network_exception_then_success(self, sleep_spy: list[float], client_factory: Any) -> None:
        seq = [httpx.ConnectTimeout("t"), _FakeResp(f"{_FINAL_URL}#508")]
        client_factory(lambda: seq.pop(0))
        url = knshow.resolve_redirect("/rd/foo")
        assert url == _FINAL_URL, "tracking hash (#508)除去"
        assert sleep_spy == [3.0]

    def test_raises_after_3_failures(self, sleep_spy: list[float], client_factory: Any) -> None:
        client_factory(lambda: (_ for _ in ()).throw(httpx.ConnectTimeout("boom")))
        with pytest.raises(httpx.ConnectTimeout):
            knshow.resolve_redirect("/rd/foo")
        assert sleep_spy == [3.0, 6.0], "最終失敗では raise（呼出側 item skip）"

    def test_success_first_attempt_no_sleep(self, sleep_spy: list[float], client_factory: Any) -> None:
        client_factory(lambda: _FakeResp(_FINAL_URL))
        assert knshow.resolve_redirect("/rd/foo") == _FINAL_URL
        assert sleep_spy == []
