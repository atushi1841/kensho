"""
Tests for kensho/scraping/source_health.py — t_442337b4 提案2/3（収集源ヘルスモニタ）。

対象仕様:
- SourceHealth: data/source_health.json にソース別 {attempts, failures, consecutive_failures,
  skipped} を日次永続化。日付が変わるとロール（連続失敗/失敗率リセット）。
- 異常判定2系統: 連続失敗>=max_consecutive_failures OR (試行>=min_attempts かつ 失敗率>=rate)。
- success で consecutive_failures リセット。skip 記録 + all_primary_idle（全主要源run内応答失敗）。
- module の note_fetch: non-active 時は no-op。
- common._fetch_with_retry: backoff が 8s にキャップされる。

ネットワーク・sleep は全て mock（tests/AGENTS.md ルール準拠）。
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import json
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.source_health import (
    PRIMARY_SOURCES,
    SourceHealth,
    get_active,
    note_fetch,
    set_active,
)


# ── 日付ロール用ヘルパー ──
def _now(day: str) -> Callable[[], datetime]:
    def _f() -> datetime:
        return datetime.fromisoformat(f"{day}T10:00:00")

    return _f


# =====================================================================
# SourceHealth — 記録・判定・ロール
# =====================================================================
class TestSourceHealth:
    def test_records_failure_and_counts_attempts(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        h.record_failure("ken-kaku", "ConnectTimeout")
        h.record_failure("ken-kaku", "ConnectTimeout")
        e = h._entry("ken-kaku")
        assert e["attempts"] == 2
        assert e["failures"] == 2
        assert e["consecutive_failures"] == 2
        assert e["last_error"] == "ConnectTimeout"

    def test_consecutive_failures_triggers_unhealthy(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, max_consecutive_failures=4, now_fn=_now("2026-09-18"))
        for _ in range(4):
            h.record_failure("cp.meikan")
        assert h.is_unhealthy("cp.meikan") is True
        # 閾値未満は healthy
        h2 = SourceHealth(tmp_path, max_consecutive_failures=5, now_fn=_now("2026-09-18"))
        for _ in range(4):
            h2.record_failure("cp.meikan")
        assert h2.is_unhealthy("cp.meikan") is False

    def test_success_resets_consecutive_failures(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, max_consecutive_failures=3, now_fn=_now("2026-09-18"))
        for _ in range(3):
            h.record_failure("ke-ma")
        assert h.is_unhealthy("ke-ma") is True
        h.record_success("ke-ma")
        assert h.is_unhealthy("ke-ma") is False
        assert h._entry("ke-ma")["consecutive_failures"] == 0

    def test_daily_failure_rate_triggers_with_min_attempts(self, tmp_path: Path) -> None:
        # 試行が min_attempts 未満なら低試行のレートを見ない（誤検知防止）
        h = SourceHealth(tmp_path, daily_failure_rate=0.5, min_attempts=6, now_fn=_now("2026-09-18"))
        # 3試行中2失敗（66%超だが min_attempts=6 未満）→ healthy
        for i in range(4):
            (h.record_failure if i < 2 else h.record_success)("kenshou.club")
        assert h.is_unhealthy("kenshou.club") is False
        # min_attempts 到達後にレート超過 → unhealthy
        h.record_failure("kenshou.club")
        h.record_failure("kenshou.club")
        # ここで attempts=6, failures=4 → 66% >= 0.5 → unhealthy
        assert h.is_unhealthy("kenshou.club") is True

    def test_daily_roll_resets_state_on_date_change(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, max_consecutive_failures=3, now_fn=_now("2026-09-18"))
        for _ in range(5):
            h.record_failure("ke-ma")
        assert h.is_unhealthy("ke-ma") is True
        # 日付が変わるとロール → counts リセット・healthy
        h2 = SourceHealth(tmp_path, max_consecutive_failures=3, now_fn=_now("2026-09-19"))
        assert h2.is_unhealthy("ke-ma") is False
        assert h2._state["date"] == "2026-09-19"
        assert h2._state["sources"].get("ke-ma") is None

    def test_record_skip_and_skipped_list(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        h.record_skip("ken-kaku")
        h.record_skip("ken-kaku")
        assert h._entry("ken-kaku")["skipped"] == 2
        assert h.skipped == ["ken-kaku"]  # 重複除外

    def test_status_line_reports_threshold(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, max_consecutive_failures=4, now_fn=_now("2026-09-18"))
        h.record_failure("cp.meikan", "ReadTimeout")
        out = h.status_line("cp.meikan")
        assert "連続失敗1/4" in out
        assert "ReadTimeout" in out
        assert h.status_line("cp.meikan2") == "データなし"

    def test_twscrape_success_rate_recorded_and_persisted(self, tmp_path: Path) -> None:
        # t_2be0e7aa: twscrape 成功率を source_health に記録し、日付ロールでも保持される。
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        h.record_twscrape_run(True)
        h.record_twscrape_run(False)
        h.record_twscrape_run(True)
        m = h._state["twscrape_success_rate"]
        assert m["runs"] == 3
        assert m["successes"] == 2
        assert abs(m["last"] - 2 / 3) < 1e-9
        # save() 後も永続化されている
        h.save()
        d = json.loads((tmp_path / "source_health.json").read_text(encoding="utf-8"))
        assert "twscrape_success_rate" in d
        assert d["twscrape_success_rate"]["runs"] == 3

    def test_twscrape_success_rate_preserved_on_daily_roll(self, tmp_path: Path) -> None:
        # t_2be0e7aa: 日付ロールで sources はリセットされるが twscrape_success_rate は累積保持
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        h.record_twscrape_run(True)
        h.record_twscrape_run(True)
        h.save()
        # 日付変更 → 新 SourceHealth でロール発動
        h2 = SourceHealth(tmp_path, now_fn=_now("2026-09-19"))
        assert h2._state["date"] == "2026-09-19"
        assert h2._state["sources"] == {}
        m = h2._state["twscrape_success_rate"]
        assert m["runs"] == 2 and m["successes"] == 2 and m["last"] == 1.0

    def test_knshow_is_primary_and_tracks_failures_to_unhealthy(self, tmp_path: Path) -> None:
        # t_52a7fec2: knshow は PRIMARY_SOURCES に含まれ、502連続>=4で異常判定されること。
        #   （以前は監視対象外=一覧502が source_health.json に蓄積されない盲点だった）
        assert "knshow" in PRIMARY_SOURCES
        h = SourceHealth(tmp_path, max_consecutive_failures=4, now_fn=_now("2026-09-18"))
        for _ in range(4):
            h.record_failure("knshow", "http=502")
        e = h._entry("knshow")
        assert e["attempts"] == 4
        assert e["failures"] == 4
        assert e["consecutive_failures"] == 4
        assert h.is_unhealthy("knshow") is True
        # 回復(200)で連続失敗リセット → healthy に戻る
        h.record_success("knshow")
        assert h.is_unhealthy("knshow") is False
        assert h._entry("knshow")["consecutive_failures"] == 0


class TestFallbackDetection:
    def test_all_primary_idle_when_no_success_and_failures(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        h.begin_run()
        for src in PRIMARY_SOURCES:
            h.record_failure(src, "ConnectTimeout")
        assert h.all_primary_idle() is True
        assert h.any_primary_failed() is True

    def test_all_primary_idle_when_all_skipped(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        h.begin_run()
        for src in PRIMARY_SOURCES:
            h.record_skip(src)
        assert h.all_primary_idle() is True

    def test_not_idle_when_any_source_succeeded(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        h.begin_run()
        h.record_success("ken-kaku")
        h.record_failure("kenshou.club")
        assert h.all_primary_idle() is False  # 1源でも成功ページあり
        assert h.any_primary_failed() is True

    def test_fresh_run_not_idle(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        h.begin_run()
        # 成功も失敗も触れていない最初の run は idle と見做さない（新着なしの正常運用）
        assert h.all_primary_idle() is False


# =====================================================================
# module レベル note_fetch / set_active
# =====================================================================
class TestActiveMonitor:
    def test_note_fetch_noop_when_no_active(self, tmp_path: Path) -> None:
        set_active(None)  # 安全のためクリア
        note_fetch("ken-kaku", True)  # 例外を投げない
        assert get_active() is None

    def test_note_fetch_records_to_active(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        set_active(h)
        try:
            note_fetch("ke-ma", True)
            note_fetch("ke-ma", False, "ConnectTimeout")
            assert h.run_successes["ke-ma"] == 1
            assert h.run_failures["ke-ma"] == 1
            assert h._entry("ke-ma")["consecutive_failures"] == 1
        finally:
            set_active(None)

    def test_note_fetch_ignores_empty_source(self, tmp_path: Path) -> None:
        h = SourceHealth(tmp_path, now_fn=_now("2026-09-18"))
        set_active(h)
        try:
            note_fetch(None, False)  # source なし → 記録しない
            assert h._state["sources"] == {}
        finally:
            set_active(None)


# =====================================================================
# common._fetch_with_retry — backoff 8s キャップ + ヘルス記録
# =====================================================================
class TestFetchWithRetryBackoff:
    @pytest.fixture()
    def setup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 常に ConnectTimeout を投げる fetch に差し替え、sleep を記録
        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise httpx.ConnectTimeout("boom")

        set_active(None)  # ヘルス記録を無効化（data/ 書き込み回避）
        self.sleeps: list[float] = []

        def _fake_sleep(s: float) -> None:
            self.sleeps.append(s)

        monkeypatch.setattr("kensho.scraping.sources.common.fetch", _boom)
        monkeypatch.setattr("kensho.scraping.sources.common.time.sleep", _fake_sleep)

    def test_backoff_capped_at_8s_and_finite(self, setup: Any) -> None:
        from kensho.scraping.sources import common

        code, html, _ = common._fetch_with_retry("https://example.invalid", max_retries=5)
        assert code == 0
        assert html == ""
        # 各 sleep は 8s + jitter(0..1) を超えない（指数バックオフの上限キャップ）
        assert self.sleeps, "リトライ間 sleep が一度も記録されていない"
        assert all(s <= 9.0 for s in self.sleeps), f"backoff が 8s を超えている: {self.sleeps}"
        # 初期 backoff = 1s + jitter(0..1) → 約1〜2s
        assert 0.9 <= self.sleeps[0] <= 2.1, f"初期 backoff は約1s+jitter: {self.sleeps[0]}"

    def test_every_attempt_attempts_network(self, setup: Any) -> None:
        from kensho.scraping.sources import common

        common._fetch_with_retry("https://example.invalid", max_retries=3)
        # 1回目のモンキーパッチ関数の呼び出し回数は確認できないため sleep 回数で間接検証:
        #   max_retries=3 → ループ内 3 fetch + 末尾 1 fetch = 4 ネットワーク試行、sleep は 2 回
        assert len(self.sleeps) == 2
