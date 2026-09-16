"""
Tests for kensho/scraping/sources/kenkaku.py — critic v144 retryロジックの恒久モックテスト。

対象仕様（commit 7448138, kenkaku.py L24-26 + critic対策）:
- _KENKAKU_MAX_RETRIES=2 / _KENKAKU_RETRY_BACKOFF=2.0（指数バックオフ: base 2.0 * 2**attempt）
- fetchのみリトライ対象。非200は即スキップ（リトライ不発火＝往来動作の回帰防止）
- 最終失敗時はそのページだけスキップ、他ページは続行
ネットワーク・sleepは全てmock（tests/AGENTS.mdルール準拠）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.sources import kenkaku
from kensho.scraping.sources.common import KENKAKU_BASE

_PAGE1: str = kenkaku._KENKAKU_PAGE_IDS[0]
_PAGE2: str = kenkaku._KENKAKU_PAGE_IDS[1]
_URL1: str = f"{KENKAKU_BASE}present.cgi?id={_PAGE1}"
_URL2: str = f"{KENKAKU_BASE}present.cgi?id={_PAGE2}"

_ITEM_HTML: str = '<html><body><a href="https://x.com/testuser/status/1234567890123">tweet</a></body></html>'
_EMPTY_HTML: str = "<html><body>no x links</body></html>"


def _resp(status: int = 200, html: str = _EMPTY_HTML) -> httpx.Response:
    return httpx.Response(
        status,
        content=html.encode("utf-8"),
        headers={"content-type": "text/html; charset=utf-8"},
    )


class _FakeSession:
    """httpx.Client互換の最小フェイスクライアント（コンテキストマネージャ）。"""

    def __init__(self, engine: _FakeClientFactory) -> None:
        self._engine = engine

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        return self._engine.respond(url)


class _FakeClientFactory:
    """URL別に Responses/Exceptions のキューをスクリプト化する httpx.Client 互換ファクトリ。

    キューが空のURL（=スクリプト外ページ）は常に 200 空HTML を返す。
    """

    def __init__(self, script: dict[str, list[Any]]) -> None:
        self._script: dict[str, list[Any]] = {u: list(q) for u, q in script.items()}
        self.calls: list[str] = []

    def __call__(self, *args: Any, **kwargs: Any) -> _FakeSession:
        return _FakeSession(self)

    def respond(self, url: str) -> httpx.Response:
        self.calls.append(url)
        queue = self._script.get(url)
        if queue:
            nxt = queue.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return cast_response(nxt)
        return _resp()


def cast_response(obj: Any) -> httpx.Response:
    assert isinstance(obj, httpx.Response)
    return obj


@pytest.fixture()
def sleep_spy(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """kenkaku.time.sleep をインターセプトし待機秒を記録（テスト短縮）。"""
    recorded: list[float] = []
    monkeypatch.setattr("kensho.scraping.sources.kenkaku.time.sleep", lambda s: recorded.append(float(s)))
    return recorded


@pytest.fixture()
def client_factory(monkeypatch: pytest.MonkeyPatch) -> Any:
    """kenkakuモジュール経由の httpx.Client をフェイクに置換するアタッチポイントを返す。"""
    holder: dict[str, _FakeClientFactory] = {}

    def install(script: dict[str, list[Any]]) -> _FakeClientFactory:
        factory = _FakeClientFactory(script)
        holder["f"] = factory
        monkeypatch.setattr("kensho.scraping.sources.kenkaku.httpx.Client", factory)
        return factory

    yield install
    # monkeypatchは自動復元


def _run_scrape() -> tuple[list[str], list[dict[str, Any]]]:
    logs: list[str] = []
    items = kenkaku.scrape_kenkaku(logs.append, set(), ["atushi16"])
    return logs, items


class TestRetryConstants:
    """リトライ定数: kenkaku.py L25-26 の v144 + critic対策（指数バックオフ）仕様との整合アサーション"""

    def test_max_retries_is_2(self) -> None:
        assert kenkaku._KENKAKU_MAX_RETRIES == 2

    def test_backoff_is_2_seconds(self) -> None:
        assert kenkaku._KENKAKU_RETRY_BACKOFF == 2.0

    def test_backoff_sleep_uses_constant(self, sleep_spy: list[float], client_factory: Any) -> None:
        client_factory({_URL1: [httpx.ConnectTimeout("t"), _resp(200, _ITEM_HTML)]})
        _run_scrape()
        # 1回目のリトライ待機 = base 2.0 * 2**0 = 2.0
        assert kenkaku._KENKAKU_RETRY_BACKOFF * (2**0) in sleep_spy


class TestRetrySuccess:
    """① ConnectTimeout→リトライ1/2→2回目で成功 → items取得されること"""

    def test_timeout_then_success_collects_items(self, sleep_spy: list[float], client_factory: Any) -> None:
        factory = client_factory({_URL1: [httpx.ConnectTimeout("boom"), _resp(200, _ITEM_HTML)]})
        logs, items = _run_scrape()

        assert any(f"ページ{_PAGE1}" in m and "リトライ1/2" in m for m in logs)
        assert not any("リトライ2/2" in m for m in logs), "2回目で成功したのに3回目のリトライログがある"
        assert not any("ERROR" in m for m in logs)
        assert len(items) == 1
        assert items[0]["x_url"] == "https://x.com/testuser/status/1234567890123"
        assert items[0]["source"] == "ken-kaku"
        assert factory.calls.count(_URL1) == 2
        # 1回目のリトライ待機 = 指数バックオフ base 2.0 * 2**0 = 2.0
        assert sum(1 for s in sleep_spy if s == kenkaku._KENKAKU_RETRY_BACKOFF) == 1, "指数バックオフ(2.0s)が1回だけ"

    def test_success_on_third_attempt(self, sleep_spy: list[float], client_factory: Any) -> None:
        # リトライ2回（=合計3アテンプト）目まで許容される
        factory = client_factory({_URL1: [httpx.ConnectTimeout("b1"), httpx.ReadTimeout("b2"), _resp(200, _ITEM_HTML)]})
        logs, items = _run_scrape()
        assert any("リトライ1/2" in m for m in logs)
        assert any("リトライ2/2" in m for m in logs)
        assert len(items) == 1
        assert factory.calls.count(_URL1) == 3


class TestFinalFailureSkipsPageOnly:
    """② 3回連続失敗 → 最終ERRORログ1回・そのページのみスキップ、他ページは続行"""

    def test_three_failures_skip_page_with_single_error_log(self, sleep_spy: list[float], client_factory: Any) -> None:
        factory = client_factory({
            _URL1: [httpx.ConnectTimeout("b") for _ in range(3)],
            _URL2: [_resp(200, _ITEM_HTML)],
        })
        logs, items = _run_scrape()

        error_lines = [m for m in logs if f"ページ{_PAGE1}: ERROR" in m]
        assert len(error_lines) == 1, f"最終ERRORログは1回のはず: {error_lines}"
        assert any("リトライ1/2" in m for m in logs)
        assert any("リトライ2/2" in m for m in logs)
        assert not any("リトライ3/2" in m for m in logs), "MAX_RETRIES=2超のリトライログは不正"
        assert factory.calls.count(_URL1) == 3
        # 他ページは続行 → PAGE2のアイテムは取得される
        assert factory.calls.count(_URL2) == 1
        assert len(items) == 1
        assert any(f"ページ{_PAGE2}" in m or "✅" in m for m in logs)
        # 失敗ページ後も0.3sの間隔維持 + 指数バックオフ（2.0s×1回 + 4.0s×1回）
        assert sum(1 for s in sleep_spy if s == kenkaku._KENKAKU_RETRY_BACKOFF) == 1, "1回目=base 2.0s"
        assert sum(1 for s in sleep_spy if s == kenkaku._KENKAKU_RETRY_BACKOFF * 2) == 1, "2回目=4.0s"
        assert any(s == 0.3 for s in sleep_spy)

    def test_total_page_calls_respect_retry_budget(self, sleep_spy: list[float], client_factory: Any) -> None:
        factory = client_factory({_URL1: [httpx.ConnectTimeout("b") for _ in range(5)]})
        _run_scrape()
        # 失敗を繰り返すページは 1+MAX_RETRIES=3 回だけ叩かれ、無限リトライしない
        assert factory.calls.count(_URL1) == 1 + kenkaku._KENKAKU_MAX_RETRIES


class TestNon200NoRetry:
    """③ HTTP非200 → リトライ不発火で即スキップ（往来動作の回帰防止）"""

    def test_http_503_skips_without_retry(self, sleep_spy: list[float], client_factory: Any) -> None:
        factory = client_factory({
            _URL1: [_resp(503), _resp(200, _ITEM_HTML)],
            _URL2: [_resp(404)],
        })
        logs, items = _run_scrape()

        # 1ページ目が2回目に成功してしまえばリトライ発火となるため、
        # 非200は1回しか叩かないこと＋スキップログ1回を検証
        assert factory.calls.count(_URL1) == 1, "非200でリトライしてはいけない"
        assert factory.calls.count(_URL2) == 1
        skip_logs = [m for m in logs if "スキップ" in m]
        assert len(skip_logs) == 2
        assert any(f"ページ{_PAGE1}: HTTP 503" in m for m in skip_logs)
        assert any(f"ページ{_PAGE2}: HTTP 404" in m for m in skip_logs)
        assert not any("リトライ" in m for m in logs), "非200でリトライログが出てはいけない"
        assert not any("ERROR" in m for m in logs), "非200は最終ERRORログ対象外（スキップログのみ）"
        assert items == []

    def test_backoff_not_used_on_non200(self, sleep_spy: list[float], client_factory: Any) -> None:
        client_factory({_URL1: [_resp(500)]})
        _run_scrape()
        assert kenkaku._KENKAKU_RETRY_BACKOFF not in sleep_spy


class TestParseErrorNotRetried:
    """パース部例外はfetch対象外 — リトライせずERROR1回で他ページ続行（v144仕様: fetchのみリトライ）"""

    def test_decode_exception_no_extra_fetch(
        self, sleep_spy: list[float], client_factory: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        factory = client_factory({_URL1: [_resp(200, _ITEM_HTML)]})

        def boom(r: httpx.Response) -> str:
            raise ValueError("decode fail")

        monkeypatch.setattr(kenkaku, "_decode_response", boom)
        logs, items = _run_scrape()
        assert factory.calls.count(_URL1) == 1, "パース例外でfetchを再試行してはいけない"
        assert any(f"ページ{_PAGE1}: ERROR ValueError" in m for m in logs)
        assert items == []
