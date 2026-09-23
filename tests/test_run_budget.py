"""t_b64c35ea: 収集runの実行時間上限（deadline）と部分保存のテスト.

背景:
    毎時収集(kensho-collect-only.sh)の flock を collect の子プロセスが保持し続けるため、
    1run が長時間化すると後続スロットが「前回の収集がまだ継続中 → スキップ」で欠落する。
    対策として 1run の実行時間上限を設け、超過時は「残ソースの打ち切り + 部分保存」を行う。

対象:
    kensho/scraping/run_budget.py — RunBudget / check_budget
    kensho/scraping/collector.py  — 予算超過時の phase 打ち切りと collected.json への記録
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping import collector
from kensho.scraping.run_budget import MARKER, RunBudget, check_budget

_SOURCE_ATTRS: tuple[str, ...] = (
    "scrape_kenkaku",
    "scrape_kenshouclub",
    "scrape_cpmeikan",
    "scrape_kema",
    "scrape_twscrape",
    "scrape_chancecom",
    "scrape_kensho_everyday",
    "scrape_kenshofan",
    "scrape_prtimes",
)


class FakeClock:
    """単調時計のスタブ（テストを実時間に依存させない）。"""

    def __init__(self) -> None:
        self.t: float = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _canned_item() -> dict[str, Any]:
    """Step2b(ken-kaku) が返す想定の収集アイテム（tweet_text入り = Step4の通信を発生させない）。"""
    return {
        "detail_url": "/d/1",
        "rd_url": "https://rd.example/1",
        "x_url": "https://x.com/foo/status/111",
        "tweet_id": "111",
        "source": "ken-kaku",
        "time": 0.1,
        "deadline": "2099-01-01",
        "winner_count": 10,
        "days_remaining": "あと99日",
        "prize_score": {},
        "applied": {"atushi16": None},
        "tweet_text": "フォロー&RTで応募",
        "keyword_flag": False,
    }


def _recorder(name: str, calls: list[str], ret: list[dict[str, Any]] | None = None) -> Any:
    """呼ばれたら記録して固定値を返すフェイク収集源。"""

    def _fn(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        calls.append(name)
        return list(ret) if ret else []

    return _fn


def _cfg(tmp_path: Path, **collection: Any) -> dict[str, Any]:
    col: dict[str, Any] = {"max_items": 5, "max_run_seconds": 1500, "llm_classify": False}
    col.update(collection)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return {
        "general": {"project_dir": str(tmp_path)},
        "accounts": [
            {"key": "atushi16", "session": "data/x_session_atushi16.json", "schedule": {"collects": True}}
        ],
        "collection": col,
    }


class _AlwaysExpired(RunBudget):
    def expired(self) -> bool:
        return True


class _ExpiredAfter(RunBudget):
    """expired() が呼ばれた回数が allowed を超えたら True（決定的に途中で打ち切る）。"""

    def __init__(self, allowed: int) -> None:
        super().__init__(1500.0)
        self._allowed = allowed
        self._calls = 0

    def expired(self) -> bool:
        self._calls += 1
        return self._calls > self._allowed


class TestRunBudget:
    """RunBudget: 経過・残り・上限到達の判定"""

    def test_not_expired_before_limit(self) -> None:
        clock = FakeClock()
        b = RunBudget(100, clock=clock)
        clock.advance(99)
        assert b.expired() is False
        assert b.remaining == pytest.approx(1.0)

    def test_expired_at_limit(self) -> None:
        clock = FakeClock()
        b = RunBudget(100, clock=clock)
        clock.advance(100)
        assert b.expired() is True
        assert b.remaining == 0.0

    def test_disabled_when_non_positive(self) -> None:
        clock = FakeClock()
        b = RunBudget(0, clock=clock)
        clock.advance(10_000)
        assert b.disabled is True
        assert b.expired() is False
        assert b.remaining == float("inf")

    def test_note_dedup_keeps_order(self) -> None:
        b = RunBudget(100, clock=FakeClock())
        b.note("A")
        b.note("B")
        b.note("A")
        assert b.expired_phases == ["A", "B"]
        assert b.elapsed == pytest.approx(0.0)


class TestCheckBudget:
    """check_budget: 打ち切り判定とログ（同一phaseは1回だけ）"""

    def test_returns_false_within_budget(self) -> None:
        logs: list[str] = []
        b = RunBudget(100, clock=FakeClock())
        assert check_budget(b, "Step1", logs.append) is False
        assert logs == []
        assert b.expired_phases == []

    def test_logs_once_and_returns_true(self) -> None:
        logs: list[str] = []
        clock = FakeClock()
        b = RunBudget(100, clock=clock)
        clock.advance(150)
        assert check_budget(b, "Step1", logs.append) is True
        assert check_budget(b, "Step1", logs.append) is True
        assert len(logs) == 1
        assert MARKER in logs[0]
        assert b.expired_phases == ["Step1"]

    def test_marks_multiple_phases(self) -> None:
        logs: list[str] = []
        clock = FakeClock()
        b = RunBudget(100, clock=clock)
        clock.advance(200)
        check_budget(b, "Step2c kenshou.club", logs.append)
        check_budget(b, "Step4 ツイート本文取得", logs.append)
        assert b.expired_phases == ["Step2c kenshou.club", "Step4 ツイート本文取得"]
        assert len(logs) == 2


class TestCollectorDeadline:
    """collector: 予算超過時に残ソースを打ち切り、部分保存と記録を行う"""

    def test_all_sources_skipped_and_partial_save(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        for attr in _SOURCE_ATTRS:
            monkeypatch.setattr(collector, attr, _recorder(attr, calls))
        monkeypatch.setattr(collector, "RunBudget", lambda *a, **k: _AlwaysExpired(1500.0))

        result = collector._collect_impl(_cfg(tmp_path))

        assert result == (0, 0, 0)
        # 予算超過時はネットワークを伴う収集源を一切呼ばない
        assert calls == []
        saved = json.loads((tmp_path / "data" / "collected.json").read_text(encoding="utf-8"))
        assert saved["deadline_exceeded"] is True
        assert saved["run_budget_seconds"] == 1500.0
        assert "Step1 knshow一覧" in saved["skipped_phases"]

    def test_cut_is_partial_what_was_collected_is_saved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ken-kaku まで収集 → そこで上限到達 → kclub以降は打ち切り、それでも保存は行われる"""
        calls: list[str] = []
        monkeypatch.setattr(collector, "fetch_listing_with_retry", lambda *a, **k: (200, "<html></html>", None))
        for attr in _SOURCE_ATTRS:
            ret = [_canned_item()] if attr == "scrape_kenkaku" else None
            monkeypatch.setattr(collector, attr, _recorder(attr, calls, ret))
        monkeypatch.setattr(collector, "check_dead_sources", lambda **k: None)
        monkeypatch.setattr("kensho.core.notifier.notify_warning", lambda *a, **k: None)
        # Step1チェック(1回目)→ken-kakuチェック(2回目)までは実行、kclubチェック(3回目)で打ち切り
        monkeypatch.setattr(collector, "RunBudget", lambda *a, **k: _ExpiredAfter(2))

        result = collector._collect_impl(_cfg(tmp_path))

        assert calls == ["scrape_kenkaku"]  # それ以降のソースは呼ばれない
        # success は knshow(Step2a) の取得成功数のみを数えるため 0（収集総数は第3要素の 1）
        assert result == (0, 0, 1)
        saved = json.loads((tmp_path / "data" / "collected.json").read_text(encoding="utf-8"))
        assert saved["deadline_exceeded"] is True
        assert "kenshou.club" in saved["skipped_phases"]
        # 部分保存 = 打ち切り前に収集できた1件は失われない
        assert [i["x_url"] for i in saved["collected"]] == ["https://x.com/foo/status/111"]
