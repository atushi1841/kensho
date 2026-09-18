"""Tests for kensho/scraping/socks_rotation.py — SOCKS5プロキシローテーション（t_f4698348 代替案）。

対象: t_f4698348 は Crawlee 統合を提案したが、実測で Crawlee 1.10.0 の ProxyConfiguration が
socks5:// を受け付けない（pydantic AnyHttpUrl=http/httpsのみ）ため任務の「失敗時の代替案」=
既存 httpx+SOCKS5 ローテーション強化を実装。本テストはそのロータ―の純関数・モック動作を検証。

ネットワーク・sleep は全て mock（tests/AGENTS.md ルール準拠）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping import socks_rotation
from kensho.scraping.socks_rotation import (
    PROXY_POOL_DEFAULT,
    SocksProxyRotator,
    make_rotator_from_config,
    proxied_fetch,
    proxied_fetch_with_retry,
)


def _rotator(pool: list[str]) -> SocksProxyRotator:
    r = SocksProxyRotator(pool=pool)
    r._pool = list(pool)  # undo __init__ shuffle → 決定的な順序 (round-robin order)
    r._idx = 0  # determinism
    return r


class TestRotator:
    def test_default_pool_nonempty(self) -> None:
        assert len(PROXY_POOL_DEFAULT) >= 4
        assert all(p.startswith("socks5h://") for p in PROXY_POOL_DEFAULT)

    def test_next_url_round_robin(self) -> None:
        r = _rotator(["p1", "p2", "p3"])
        assert r.next_url() == "p1"
        assert r.next_url() == "p2"
        assert r.next_url() == "p3"
        assert r.next_url() == "p1"  # wrap

    def test_mark_fail_cooldown_skips_then_recovers(self) -> None:
        r = _rotator(["p1", "p2"])
        r.mark_fail("p1", now=1000.0)  # クールダウン 5分 → 1300 まで p1 除外
        # p1 -> p2 -> p1(=クールダウン中) -> p2 ... の順で、p1 はしばらく出ない
        got = {r.next_url(now=1100.0) for _ in range(6)}
        assert "p1" not in got
        assert "p2" in got
        # クールダウン解消後は p1 に復帰できる
        assert r.next_url(now=1400.0) == "p1"

    def test_alpha_counts_active_dead(self) -> None:
        r = _rotator(["p1", "p2", "p3"])
        r.mark_fail("p1", now=1000.0)
        alive, dead = r.alpha(now=1001.0)
        assert alive == 2
        assert dead == 1

    def test_empty_pool_returns_none(self) -> None:
        r = _rotator([])
        assert r.next_url() is None
        assert r.alpha() == (0, 0)

    def test_make_rotator_from_config(self) -> None:
        assert make_rotator_from_config(None) is None
        assert make_rotator_from_config({"collection": {}}) is None
        r = make_rotator_from_config({"collection": {"proxy_pool": ["socks5://x:1"]}})
        assert r is not None
        assert r.pool == ["socks5://x:1"]


class TestProxiedFetch:
    def test_passes_proxy_and_returns_tuple(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        class _FakeResp:
            status_code = 200
            url = "http://fake/"

            def __init__(self) -> None:
                self.content = b"<html>hi</html>"
                self.encoding = "utf-8"
                self.text = "<html>hi</html>"

        class _FakeClient:
            def __init__(self, **kwargs: Any) -> None:
                captured["kwargs"] = kwargs

            def __enter__(self) -> _FakeClient:
                return self

            def __exit__(self, *a: Any) -> None:
                return None

            def get(self, url: str, headers: Any = None) -> _FakeResp:
                captured["url"] = url
                captured["headers"] = headers
                return _FakeResp()

        monkeypatch.setattr(socks_rotation.httpx, "Client", _FakeClient)
        code, html, final = proxied_fetch("http://x/", referer="http://ref/", timeout=5, proxy="socks5h://p:1")
        assert code == 200
        assert html == "<html>hi</html>"
        assert final == "http://fake/"
        assert captured["kwargs"]["proxy"] == "socks5h://p:1"
        assert captured["kwargs"]["timeout"] == 5
        assert captured["headers"]["Referer"] == "http://ref/"


class TestProxiedFetchWithRetry:
    @pytest.fixture()
    def no_sleep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socks_rotation.time, "sleep", lambda s: None)

    def test_success_first_proxy(self, no_sleep: None, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        monkeypatch.setattr(
            socks_rotation,
            "proxied_fetch",
            lambda url, referer=None, timeout=10, proxy=None: (
                calls.append(proxy or "DIRECT"),
                (200, "<ok>", url),
            )[1],
        )
        code, html, _ = proxied_fetch_with_retry("http://x/", max_retries=1, rotator=_rotator(["p1"]))
        assert code == 200
        assert html == "<ok>"
        assert calls == ["p1"]

    def test_rotates_when_proxy_fails(self, no_sleep: None, monkeypatch: pytest.MonkeyPatch) -> None:
        # p1 が0（ネットワークエラー相当）、p2 が200
        def fake(url: str, referer=None, timeout=10, proxy=None) -> tuple[int, str, str]:
            if proxy == "p1":
                return (0, "", "")
            return (200, "ok2", url)

        monkeypatch.setattr(socks_rotation, "proxied_fetch", fake)
        code, html, _ = proxied_fetch_with_retry("http://x/", max_retries=3, rotator=_rotator(["p1", "p2"]))
        assert code == 200
        assert html == "ok2"

    def test_all_fail_falls_back_to_direct(self, no_sleep: None, monkeypatch: pytest.MonkeyPatch) -> None:
        results = {
            "p1": (0, "", ""),
            "p2": (0, "", ""),
            None: (200, "direct", "http://d/"),
        }
        calls: list[str] = []

        def fake(url: str, referer=None, timeout=10, proxy=None) -> tuple[int, str, str]:
            calls.append(proxy or "DIRECT")
            return results[proxy]

        monkeypatch.setattr(socks_rotation, "proxied_fetch", fake)
        r = _rotator(["p1", "p2"])
        code, html, final = proxied_fetch_with_retry("http://x/", max_retries=2, rotator=r)
        assert code == 200
        assert html == "direct"
        assert final == "http://d/"
        assert calls[-1] == "DIRECT"  # 直接フォールバック
        _, dead = r.alpha()
        assert dead == 2  # p1, p2 ともクールダウン

    def test_no_rotator_uses_default_pool(self, no_sleep: None, monkeypatch: pytest.MonkeyPatch) -> None:
        # rotator=None → 既定プールから1台試行。失敗時はダイレクトへ。
        called: list[str] = []

        def fake(url: str, referer=None, timeout=10, proxy=None) -> tuple[int, str, str]:
            called.append(proxy or "DIRECT")
            return (200, "z", url) if proxy else (200, "z-direct", url)

        monkeypatch.setattr(socks_rotation, "proxied_fetch", fake)
        code, html, _ = proxied_fetch_with_retry("http://x/", max_retries=1)
        assert code == 200
        assert called  # 何らかのプロキシ or 直接で1回は fetch
