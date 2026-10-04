"""Kensho SOCKS5 Proxy Rotation — 収集fetch層のプロキシローテーション強化（t_f4698348 代替案）

背景:
  t_f4698348 は Crawlee Python を収集パイプラインへ統合し SOCKS5 プロキシローテーションを
  実現する提案だった。実測の結果、Crawlee 1.10.0 の ProxyConfiguration は socks5:// を
  受け付けない（pydantic AnyHttpUrl = http/https のみ。proxy_urls / new_url_function /
  tiered_proxy_urls の全経路で reject）ため、既存 SOCKS5 基盤(SOCKS5h://172.26.80.1:108x)
  との互換性が無い。任務が定める「失敗時の代替案」＝ 既存 httpx + SOCKS5 でプロキシ
  ローテーション強化を実装する（低リスク戻し）。

本モジュール:
  - SocksProxyRotator: プロキシURLプールを round-robin で回し、失敗プロキシはクールダウン
    で除外し成功で復帰させる軽量ロータ―。
  - proxied_fetch(): httpx.Client(proxy=...) で SOCKS5 経由の fetch。（code, html, final_url）
    を返し、common.fetch() と互換。
  - proxied_fetch_with_retry(): ProxyCollapse しても全プロキシ失敗なら元の重みで省く原則に従い、
    プロキシを順に試し、それでも失敗なら直接fetch（直結・失敗時は素通し）にフォールバック。

インターフェース互換: common.fetch() / common._fetch_with_retry() と同じ
  (code:int, html:str, final_url:str)。collector.py の _do_fetch 選択肢に加える事ができる。

使い方:
  from kensho.scraping.socks_rotation import (
      proxied_fetch, proxied_fetch_with_retry, SocksProxyRotator,
      make_rotator_from_config, PROXY_POOL_DEFAULT
  )
  proxied_fetch(url, referer=None, timeout=10, proxy="socks5h://172.26.80.1:1081")
"""

from __future__ import annotations

import random
import time
from typing import Any

import httpx

try:
    import socks  # noqa: F401 — PySocks が無くても httpx は socksio で socks5 対応可能
except ImportError:  # pragma: no cover
    pass

# ── 既定プロキシプール（kensho/utils/check_proxies.py の PROXY_MAP と同系。用途は収集ソース用）──
# socks5h = リモートDNS解決（プロキシ側解決）。ブラウザ/curl と同一挙動。
PROXY_POOL_DEFAULT: list[str] = [
    "socks5h://172.26.80.1:1081",  # atushi16 (wired)
    "socks5h://172.26.80.1:1082",  # kudou
    "socks5h://172.26.80.1:1084",  # zin20120731
    "socks5h://172.26.80.1:1085",  # TankanNotes
    "socks5h://172.26.80.1:1087",  # toushiwatch
]

_DEAD_COOLDOWN_S: float = 300.0  # 失敗プロキシを5分クールダウン（再試行で自然回復を許容）


class SocksProxyRotator:
    """SOCKS5 プロキシURLプールを round-robin で回し、失敗をクールダウン除外するロータ―。

    Thread-safe ではないが、収集は単一プロセスまでなので許容（必要なら lock 追加）。
    """

    def __init__(self, pool: list[str] | None = None) -> None:
        self._pool: list[str] = list(pool) if pool is not None else list(PROXY_POOL_DEFAULT)
        # 索引はシャッフル開始（プール先頭集中を避ける）
        random.shuffle(self._pool)
        self._idx: int = 0
        self._dead_until: dict[str, float] = {}
        self._health: dict[str, bool] = {}

    @property
    def pool(self) -> list[str]:
        return list(self._pool)

    def next_url(self, now: float | None = None) -> str | None:
        """次に試すプロキシURL。全プロキシがクールダウン中なら None（=直接fetchへ）。"""
        now = now or time.time()
        if not self._pool:
            return None
        attempts: int = len(self._pool)
        for _ in range(attempts):
            url = self._pool[self._idx % len(self._pool)]
            self._idx += 1
            until = self._dead_until.get(url, 0.0)
            if until <= now:
                return url
        # 全部クールダウン中 → 早い順で1つだけ試す（前回失敗時刻が最も古いもの）
        earliest = min(self._dead_until.items(), key=lambda kv: kv[1], default=(self._pool[0], 0.0))
        return earliest[0]

    def mark_ok(self, url: str) -> None:
        self._dead_until.pop(url, None)
        self._health[url] = True

    def mark_fail(self, url: str, now: float | None = None) -> None:
        self._dead_until[url] = (now or time.time()) + _DEAD_COOLDOWN_S
        self._health[url] = False

    def alpha(self, now: float | None = None) -> tuple[int, int]:
        """稼働中(生)/クールダウン中(死) のプロキシ数。ログ表示・監視用。"""
        now = now or time.time()
        alive = sum(1 for u in self._pool if self._dead_until.get(u, 0.0) <= now)
        return alive, max(0, len(self._pool) - alive)

    def reset(self) -> None:
        self._dead_until.clear()
        self._health.clear()


def make_rotator_from_config(cfg: dict[str, Any] | None) -> SocksProxyRotator | None:
    """config.yaml の collection.proxy_pool があればロータ―生成。(-1)未設定で None。"""
    if not cfg:
        return None
    col = cfg.get("collection") or {}
    urls: Any = col.get("proxy_pool")
    if not urls:
        return None
    return SocksProxyRotator(pool=[str(u) for u in urls])


def proxied_fetch(
    url: str,
    referer: str | None = None,
    timeout: int = 10,
    proxy: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """SOCKS5 プロキシ経由で URL を取得。common.fetch() 互換 (code, html, final_url)。

    proxy 未指定でも要求は行う（既定はダイレクト相当＝httpx不用意な proxy 無し）。
    headers を渡すと UA ローテーション外の追加ヘッダを反映（knshow 詳細等では referer を使用）。
    """
    h: dict[str, str] = dict(headers) if headers else {}
    if referer:
        h["Referer"] = referer
    kwargs: dict[str, Any] = {"timeout": timeout}
    if proxy:
        kwargs["proxy"] = proxy
    with httpx.Client(follow_redirects=True, **kwargs) as c:
        r = c.get(url, headers=h or None)
        from kensho.scraping.sources.common import _decode_response

        html: str = _decode_response(r)
        return r.status_code, html, str(r.url)


def proxied_fetch_with_retry(
    url: str,
    referer: str | None = None,
    max_retries: int = 3,
    timeout: int = 10,
    rotator: SocksProxyRotator | None = None,
) -> tuple[int, str, str]:
    """プロキシを順に試し、全滅なら直接fetchへフォールバックする安定fetch。

    方針:
      - rotator 未指定でも1台の SOCKS5 プロキシ（プール先頭）で試行し、失敗時はダイレクト。
      - SOCKS5 は DNS 解決（socks5h）でプロキシ側に寄るため、ConnectTimeout(count) の
        分散化に寄与。全滅時はダイレクトを維持（[FAILOVER] 検出の機会を残す）。
    """
    if rotator is None:
        rotator = SocksProxyRotator()
    last: tuple[int, str, str] = (0, "", "")
    code: int = 0
    html: str = ""
    final: str = ""
    # プロキシを順番に round-robin で試す（max_retries 台まで）
    for attempt in range(max(1, max_retries)):
        proxy = rotator.next_url() if rotator.pool else None
        if proxy:
            try:
                code, html, final = proxied_fetch(url, referer=referer, timeout=timeout, proxy=proxy)
            except Exception:  # noqa: BLE001
                rotator.mark_fail(proxy)
                code, html, final = (0, "", "")
            if code and code < 500:
                rotator.mark_ok(proxy)
                return code, html, final
            if code == 0:
                rotator.mark_fail(proxy)
            last = (code, html, final)
            if attempt < max(1, max_retries) - 1:
                delay: float = min((2**attempt), 4.0) + random.uniform(0, 0.5)
                time.sleep(delay)
    # 全プロキシ失敗 → 直接fetchフォールバック（収集を止めない、[FAILOVER]検出機会を残す）
    try:
        code, html, final = proxied_fetch(url, referer=referer, timeout=timeout)
    except Exception:  # noqa: BLE001
        return last if last[0] else (0, "", "")
    return code, html, final
