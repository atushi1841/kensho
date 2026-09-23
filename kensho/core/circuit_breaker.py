"""circuit_breaker — 外部依存（LLMプロバイダ呼び出し等）の連続失敗を「遮断」する。

背景 (t_96c94435 / 2026-09-23):
- モデルプロバイダの不安定稼働が常態化している: bai残高0で全死（9/18実測）、
  OpenRouter無料枠は15-21時に日次上限枯渇、nous/fireworks で404/NoneType多発。
- 従来はプロバイダ固定・フォールバック判断が都度コード依存で、死んでいる
  プロバイダへ毎バッチ「冷たい呼び出し」を続け、無駄な再試行・レイテンシ・
  429消費・ログノイズを生んでいた。

設計（Martin Fowler CircuitBreaker / MS Learn Retry pattern）:
    closed ──(連続失敗 failure_threshold 回)──▶ open
       ▲                                        │
       │                                  (cooldown 経過)
    record_success                          ▼
       └────────────────────────────── half_open（プローブ1回のみ許可）
                                          │
                                   失敗 → open（cooldown を backoff 倍で延長）

- 遮断中 (open) の `allow()` は False → 呼び出し側は冷たい再試行をせず、
  即フォールバック（次候補プロバイダ／fail-open）へ回す。遮断中の再試行は 0件。
- クールダウン経過後は half-open でプローブ1回だけ再試行（backoff 再試行）。
  成功で closed に復帰、失敗でクールダウンを `backoff_multiplier` 倍に延長。
- 閾値・クールダウンは config.yaml (`collection.llm_breaker`) と環境変数
  (`KENSHO_LLM_BREAKER_*`) で動的調整できる。

禁止領域には触れない: プロバイダの優先順・モデル名・応募ロジックは変更しない
（本モジュールが決めるのは「呼ぶか否か」と「待ち時間」のみ）。

出典:
    - https://martinfowler.com/bliki/CircuitBreaker.html
    - https://learn.microsoft.com/en-us/azure/architecture/patterns/retry
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

State = Literal["closed", "open", "half_open"]

DEFAULT_CONFIG_PATH: Path = Path(__file__).parent.parent.parent / "config.yaml"
CONFIG_SECTION: tuple[str, str] = ("collection", "llm_breaker")
ENV_PREFIX: str = "KENSHO_LLM_BREAKER_"


def _as_float(value: Any, default: float) -> float:
    """任意値をfloat化（不正値・None・bool混入は既定値へフォールバック）。"""
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class BreakerConfig:
    """遮断閾値（config.yaml / 環境変数で動的調整できる）。"""

    failure_threshold: int = 3
    cooldown_seconds: float = 300.0
    backoff_multiplier: float = 2.0
    max_cooldown_seconds: float = 3600.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> BreakerConfig:
        """dict/None から構築。欠落・不正値は既定値（＝既存挙動を壊さない）。"""
        if not data:
            return cls()
        return cls(
            failure_threshold=max(1, _as_int(data.get("failure_threshold"), 3)),
            cooldown_seconds=max(0.0, _as_float(data.get("cooldown_seconds"), 300.0)),
            backoff_multiplier=max(1.0, _as_float(data.get("backoff_multiplier"), 2.0)),
            max_cooldown_seconds=max(0.0, _as_float(data.get("max_cooldown_seconds"), 3600.0)),
        )


class CircuitBreaker:
    """1つの外部依存（プロバイダ）に対する遮断器。

    使い方（呼び出し側の定型）::

        if breaker.allow():
            try:
                result = call_provider()      # 冷たい呼び出し
            except Exception:
                breaker.record_failure()      # 連続失敗を数える
            else:
                breaker.record_success()
        else:
            ...                               # 遮断中 → 即フォールバック（再試行0件）

    `clock` は単体テスト用の時刻注入（既定は `time.monotonic`）。
    """

    def __init__(
        self,
        name: str,
        config: BreakerConfig | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.name = name
        self.config: BreakerConfig = config or BreakerConfig()
        self._clock: Callable[[], float] = clock or time.monotonic
        self._state: State = "closed"
        self._consecutive_failures: int = 0
        self._opened_at: float = 0.0
        self._cooldown: float = self.config.cooldown_seconds
        self._backoff_step: int = 0
        self._open_count: int = 0
        self._probe_in_flight: bool = False
        self._blocked_count: int = 0
        self._total_failures: int = 0
        self._total_successes: int = 0

    # ── 状態照会 ──
    @property
    def state(self) -> State:
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def blocked_count(self) -> int:
        """遮断により拒否した呼び出し回数（＝防いだ冷たい再試行の件数）。"""
        return self._blocked_count

    @property
    def open_count(self) -> int:
        return self._open_count

    @property
    def cooldown_seconds(self) -> float:
        return self._cooldown

    def cooldown_remaining(self) -> float:
        """遮断解除までの残り秒（closed/half_open は 0）。"""
        if self._state != "open":
            return 0.0
        return max(0.0, self._cooldown - (self._clock() - self._opened_at))

    # ── ゲート ──
    def allow(self) -> bool:
        """呼び出しを許可するか。遮断中は False（＝冷たい再試行をしない）。"""
        if self._state == "closed":
            return True
        if self._state == "open":
            if self._clock() - self._opened_at >= self._cooldown:
                # クールダウン経過 → 半開にしてプローブ1回だけ通す（backoff再試行）
                self._state = "half_open"
                self._probe_in_flight = True
                return True
            self._blocked_count += 1
            return False
        # half_open: 先行プローブが飛んでいる間は拒否（多重プローブ禁止）
        self._blocked_count += 1
        return False

    # ── 結果記録 ──
    def record_success(self) -> None:
        """成功で閉じる（連続失敗カウンタ・backoff段数をリセット）。"""
        self._total_successes += 1
        self._consecutive_failures = 0
        self._backoff_step = 0
        self._cooldown = self.config.cooldown_seconds
        self._probe_in_flight = False
        self._state = "closed"

    def record_failure(self) -> None:
        """失敗を数え、閾値到達で遮断（open）／half-open失敗でクールダウン延長。"""
        self._total_failures += 1
        self._probe_in_flight = False
        self._consecutive_failures += 1
        if self._state == "half_open":
            self._open()  # プローブ失敗 → 再遮断（backoff倍に延長）
            return
        if self._state == "open":
            self._open()  # 遮断中に届いた失敗（稀）→ さらに延長
            return
        if self._consecutive_failures >= self.config.failure_threshold:
            self._open()

    def snapshot(self) -> dict[str, Any]:
        """構造化ログ・health指標用の読取専用スナップショット。"""
        return {
            "name": self.name,
            "state": self._state,
            "consecutive_failures": self._consecutive_failures,
            "blocked_count": self._blocked_count,
            "open_count": self._open_count,
            "cooldown_seconds": round(self._cooldown, 3),
            "cooldown_remaining": round(self.cooldown_remaining(), 3),
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
        }

    def _open(self) -> None:
        """遮断状態へ遷移し、backoff段数に応じてクールダウンを決める。"""
        self._state = "open"
        self._opened_at = self._clock()
        self._open_count += 1
        self._cooldown = min(
            self.config.cooldown_seconds * (self.config.backoff_multiplier**self._backoff_step),
            self.config.max_cooldown_seconds,
        )
        self._backoff_step += 1


# ════════════════════════════════════════════
# プロセス内レジストリ（プロバイダ別に共有）
# ════════════════════════════════════════════

_BREAKERS: dict[str, CircuitBreaker] = {}
_CONFIG_CACHE: dict[str, tuple[float, BreakerConfig]] = {}


def _read_section(path: Path) -> Mapping[str, Any] | None:
    """config.yaml から `collection.llm_breaker` セクションを読む（不正・欠落はNone）。"""
    try:
        with open(path, encoding="utf-8") as f:
            raw: Any = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None
    node: Any = raw
    for key in CONFIG_SECTION:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, dict) else None


def _apply_env(base: BreakerConfig) -> BreakerConfig:
    """環境変数（KENSHO_LLM_BREAKER_*）で閾値を動的上書きする。"""
    data: dict[str, Any] = {}
    if f"{ENV_PREFIX}THRESHOLD" in os.environ:
        data["failure_threshold"] = os.environ[f"{ENV_PREFIX}THRESHOLD"]
    if f"{ENV_PREFIX}COOLDOWN_SECONDS" in os.environ:
        data["cooldown_seconds"] = os.environ[f"{ENV_PREFIX}COOLDOWN_SECONDS"]
    if f"{ENV_PREFIX}BACKOFF_MULTIPLIER" in os.environ:
        data["backoff_multiplier"] = os.environ[f"{ENV_PREFIX}BACKOFF_MULTIPLIER"]
    if f"{ENV_PREFIX}MAX_COOLDOWN_SECONDS" in os.environ:
        data["max_cooldown_seconds"] = os.environ[f"{ENV_PREFIX}MAX_COOLDOWN_SECONDS"]
    if not data:
        return base
    merged: dict[str, Any] = {
        "failure_threshold": base.failure_threshold,
        "cooldown_seconds": base.cooldown_seconds,
        "backoff_multiplier": base.backoff_multiplier,
        "max_cooldown_seconds": base.max_cooldown_seconds,
        **data,
    }
    return BreakerConfig.from_mapping(merged)


def load_breaker_config(path: str | Path | None = None) -> BreakerConfig:
    """遮断閾値を解決する: config.yaml `collection.llm_breaker` → env上書き → 既定値。

    mtime が変わればキャッシュを捨てる（config編集が実行中プロセスにも反映される）。
    """
    resolved = Path(path) if path else DEFAULT_CONFIG_PATH
    try:
        mtime = resolved.stat().st_mtime
    except OSError:
        mtime = 0.0
    base: BreakerConfig
    cached = _CONFIG_CACHE.get(str(resolved))
    if cached is not None and mtime and cached[0] == mtime:
        base = cached[1]
    else:
        base = BreakerConfig.from_mapping(_read_section(resolved))
        if mtime:
            _CONFIG_CACHE[str(resolved)] = (mtime, base)
    return _apply_env(base)


def get_breaker(name: str, config: BreakerConfig | None = None) -> CircuitBreaker:
    """プロバイダ名でプロセス内共有の遮断器を取得（初回にconfig.yamlから遅延ロード）。

    `config` を明示すると、その値を既存の遮断器にも即反映する（動的調整）。
    """
    resolved = config if config is not None else load_breaker_config()
    existing = _BREAKERS.get(name)
    if existing is None:
        _BREAKERS[name] = CircuitBreaker(name, resolved)
    elif existing.config != resolved:
        existing.config = resolved
    return _BREAKERS[name]


def snapshots() -> dict[str, dict[str, Any]]:
    """全遮断器のスナップショット（observability/health指標用）。"""
    return {name: b.snapshot() for name, b in _BREAKERS.items()}


def reset_all() -> None:
    """レジストリを空にする（テスト隔離・日次リセット用。閾値キャッシュは保持）。"""
    _BREAKERS.clear()
