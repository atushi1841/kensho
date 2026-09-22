"""Kensho Source Health Monitor — 収集源単位のネットワークヘルス追跡（t_442337b4 提案2・3）

背景（実測）:
  収集ログで ConnectTimeout が 1日あたり 47 件（全4源同時: KENKAKU=14 KCLUB=12 KEMA=10
  CPMK=11）観測。WSL ネットワーク層の不安定が収集漏れの主因。
  既存の dead_source_sentinel（critic v71）は「新規0件」基準でソースのサイレント死を検知する
  が、ネットワーク層の（timeout/5xx）とは別軸。本モジュールは fetch 層の応答結果を
  ソース単位で日次集計し、閾値超過で自動 skip ＋ キャッシュ（前日収集）維持に切り替える。

仕組み:
  - state JSON（data/source_health.json）へソース別 {attempts, failures,
    consecutive_failures, last_error, last_failure, skipped} を永続化。日付が変わったら
    日次ロール（閾値の水膨れ防止）。
  - 異常判定は2系統:
      1. consecutive_failures >= health_max_consecutive_failures（連続失敗）
      2. attempts >= health_min_attempts かつ failures/attempts >= health_daily_failure_rate（日次率）
    どちらかを満たすソースを unhealthy とし、collect() が次回以降そのソースを
    自動 skip（ネットワーク呼び出しを回避）する。既収集分（collected.json 累積）がそのまま
    キャッシュ＝前日データとして維持される。
  - run（collect() 1回）内の成功/失敗ページ数も保持し、全主要ソースが1つも成功ページを
    得なかった場合（全timeout or 全異常skip）に [FALLBACK] アラートを発火する（提案3）。

閾値は config.yaml の collection.health_* （任意・欠落時は本ファイルのデフォルト）。
fail-open: state 保存失敗・破損で収集本体は止めない。

使い方:
  from kensho.scraping.source_health import SourceHealth, set_active, note_fetch
  health = SourceHealth(data_dir, cfg=cfg); set_active(health)
  ... collect() 内部で note_fetch(source, succeeded) を共有fetchから呼ぶ ...
  health.save()  # 終了時
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

STATE_FILENAME: str = "source_health.json"

# 主要源（WSLネットワーク層不安定の主犯）＋ knshow（t_52a7fec2: 502日次連続で監視対象外だった
# 事故の再発防止 → PRIMARY_SOURCES へ追加し、任意主要源の連続失敗でも通知が発火するよう統合）。
# knshow 一覧ページ単体502でも集計に入り、連続>=4で unhealthy + Telegram 通知される。
# new_items_by_source のキー体系と一致。
PRIMARY_SOURCES: tuple[str, ...] = ("knshow", "ken-kaku", "kenshou.club", "cp.meikan", "ke-ma", "kenshofan")

# デフォルト閾値（collection.health_* で上書き可）
_DEF_MAX_CONSECUTIVE: int = 4  # 連続失敗がこれを超えたら異常判定
_DEF_DAILY_RATE: float = 0.5  # 日次失敗率がこれを超えたら異常判定
_DEF_MIN_ATTEMPTS: int = 6  # レート判定に必要な最小試行数（少なすぎると誤検知）


class SourceHealth:
    """ソース単位のネットワークヘルスを追跡する状態機械。"""

    def __init__(
        self,
        data_dir: str | Path,
        max_consecutive_failures: int = _DEF_MAX_CONSECUTIVE,
        daily_failure_rate: float = _DEF_DAILY_RATE,
        min_attempts: int = _DEF_MIN_ATTEMPTS,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._path: Path = Path(data_dir) / STATE_FILENAME
        self._max_cons: int = max_consecutive_failures
        self._rate: float = daily_failure_rate
        self._min_att: int = min_attempts
        self._now: Callable[[], datetime] = now_fn or datetime.now
        self._state: dict[str, Any] = self._load()
        self._roll_date()
        # 実行単位（collect() 1回）内の結果をフォールバック判定に使う（永続化しない）
        self.run_successes: dict[str, int] = {}
        self.run_failures: dict[str, int] = {}
        self.skipped: list[str] = []

    # ── state 入出力 ──
    def _date(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def _load(self) -> dict[str, Any]:
        try:
            if self._path.exists():
                data: Any = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("sources"), dict):
                    return data
        except Exception:  # noqa: BLE001 — fail-open
            pass
        return {"date": self._date(), "sources": {}}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except Exception:  # noqa: BLE001 — fail-open
            pass

    def _roll_date(self) -> None:
        """日付が変わったら新規ロール（連続失敗/失敗率をリセット）。"""
        if self._state.get("date") != self._date():
            self._state = {"date": self._date(), "sources": {}, "last_roll": self._state.get("date")}
            self._save()

    def _entry(self, source: str) -> dict[str, Any]:
        sources = cast(dict[str, dict[str, Any]], self._state.setdefault("sources", {}))
        return sources.setdefault(
            source,
            {"attempts": 0, "failures": 0, "consecutive_failures": 0, "skipped": 0},
        )

    # ── 記録 ──
    def begin_run(self) -> None:
        self.run_successes = {}
        self.run_failures = {}
        self.skipped = []

    def record_attempt(self, source: str) -> None:
        self._entry(source)["attempts"] += 1
        self.run_failures.setdefault(source, 0)

    def record_success(self, source: str) -> None:
        e = self._entry(source)
        e["attempts"] += 1
        e["consecutive_failures"] = 0  # 成功で連続失敗リセット
        self.run_successes[source] = self.run_successes.get(source, 0) + 1

    def record_failure(self, source: str, error_type: str = "network") -> None:
        e = self._entry(source)
        e["attempts"] += 1
        e["failures"] += 1
        e["consecutive_failures"] += 1
        e["last_error"] = error_type
        e["last_failure"] = self._now().isoformat(timespec="seconds")
        self.run_failures[source] = self.run_failures.get(source, 0) + 1

    def record_skip(self, source: str) -> None:
        self._entry(source)["skipped"] += 1
        if source not in self.skipped:
            self.skipped.append(source)

    # ── フェイルオーバー記録 (t_1cae393c) ──
    def record_failover(self, source: str, recovered: int) -> None:
        """KENKAKU失敗時のCPMK/KEMA補完収集を記録。"""
        e = self._entry(source)
        e["failover_count"] = e.get("failover_count", 0) + 1
        e["failover_recovered"] = e.get("failover_recovered", 0) + recovered

    # ── 判定 ──
    def is_unhealthy(self, source: str) -> bool:
        if source not in self._state["sources"]:
            return False
        e = self._entry(source)
        if int(e["consecutive_failures"]) >= self._max_cons:
            return True
        attempts = int(e["attempts"])
        failures = int(e["failures"])
        return bool(attempts >= self._min_att and failures / attempts >= self._rate)

    def status_line(self, source: str) -> str:
        if source not in self._state["sources"]:
            return "データなし"
        e = self._entry(source)
        return (
            f"連続失敗{e['consecutive_failures']}/{self._max_cons}, "
            f"日次{e['failures']}/{e['attempts']}試行"
            f"（直近エラー: {e.get('last_error', '-')}）"
        )

    def unhealthy_sources(self) -> list[str]:
        return [s for s in self._state["sources"] if self.is_unhealthy(s)]

    # ── フォールバック判定（提案3: 全主要源timeout時）──
    def any_primary_failed(self, keys: tuple[str, ...] = PRIMARY_SOURCES) -> bool:
        return any(self.run_failures.get(k, 0) > 0 for k in keys)

    def all_primary_idle(self, keys: tuple[str, ...] = PRIMARY_SOURCES) -> bool:
        """run内で全主要源が1つも成功ページを得ていない（全timeout or 全異常skip）。"""
        all_no_success: bool = all(self.run_successes.get(k, 0) == 0 for k in keys)
        touched: bool = self.any_primary_failed(keys) or bool(self.skipped)
        return bool(all_no_success and touched)

    def save(self) -> None:
        self._state["last_run"] = self._now().isoformat(timespec="seconds")
        self._state["skipped_this_run"] = list(self.skipped)
        self._save()


# ── モジュールレベルのアクティブ監視（collect() が設定、共有 fetch から参照）──
_active: SourceHealth | None = None


def set_active(health: SourceHealth | None) -> None:
    """collect() の開始時にアクティブ監視を設定（None で解除＝テスト等で無効化）。"""
    global _active
    _active = health


def get_active() -> SourceHealth | None:
    return _active


def note_fetch(source: str | None, succeeded: bool, error_type: str = "network") -> None:
    """共有 fetch 層から呼ばれる軽量レコード。source 未指定 or 非アクティブ時は無視。"""
    if not source:
        return
    health = _active
    if health is None:
        return
    if succeeded:
        health.record_success(source)
    else:
        health.record_failure(source, error_type)
