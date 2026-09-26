"""t_3ecce448: twscrape dead-skip / zero_streak が research外run で増分しないことの回帰テスト.

背景（2026-09-26 QA実測）:
    collector Step2f の dead-skip（zero_streak>=3 でAPIスキップ）が research_hours 分離判定
    より先に評価され、さらに collector は research外run でも new_items_by_source["twscrape"]=0 を
    必ず返すため dead_source_sentinel が zero_streak を毎回 +1 していた。
    結果 z は 9/26 の research外run だけで 0→4 に達し、9/27 03:00（research_hours=[3] の
    唯一の実行機会）でも skip が優先発火 → twscrape が永久に復帰できない状態だった。

修正（kensho/scraping/collector.py）:
    1. research_allowed 判定を dead-skip より先に評価し、research外では dead-skip を評価・出力しない
    2. research外 run では new_items_by_source に "twscrape" キーを持たせない
       → sentinel の `if src not in by_source: continue` が機能し zero_streak 不変
       （research run 内の dead-skip/budget では 0 を渡して増分を維持し、
         [DEAD-SOURCE] アラート経路＝観測可能性は残す）
    3. record_twscrape_run は「scrape_twscrape を試行した run」のみ記録（成功率の汚染解除）
    4. data/dead_source_state.json の twscrape zero_streak を 0 にリセット（本体の是正）
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping import collector

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


class _BufLog:
    """LogWriter 互換のメモリログ（_collect_impl(log=...) 用）。"""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, msg: str) -> None:
        self.lines.append(str(msg))

    def text(self) -> str:
        return "\n".join(self.lines)


def _canned_item() -> dict[str, Any]:
    """ken-kaku が返す想定アイテム（tweet_text入り = Step4の通信を発生させない）。"""
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
    def _fn(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        calls.append(name)
        return list(ret) if ret else []

    return _fn


def _cfg(tmp_path: Path, research_hours: list[int]) -> dict[str, Any]:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return {
        "general": {"project_dir": str(tmp_path)},
        "accounts": [
            {"key": "atushi16", "session": "data/x_session_atushi16.json", "schedule": {"collects": True}}
        ],
        "collection": {
            "max_items": 5,
            "max_run_seconds": 1500,
            "llm_classify": False,
            "research_hours": research_hours,
        },
    }


def _seed_dead_state(tmp_path: Path, zero_streak: int) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "dead_source_state.json").write_text(
        json.dumps(
            {
                "sources": {
                    "twscrape": {"zero_streak": zero_streak, "ever_positive": True, "alerted": False}
                },
                "created_tasks": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    research_hours: list[int],
    tw_ret: list[dict[str, Any]] | None = None,
) -> tuple[_BufLog, dict[str, Any], dict[str, Any]]:
    """収集を1回実行し (ログ, sentinel呼び出し引数, saved collected.json) を返す。"""
    calls: list[str] = []
    monkeypatch.setattr(
        collector, "fetch_knshow_listing", lambda *a, **k: (200, "<html></html>", None, "ok")
    )
    for attr in _SOURCE_ATTRS:
        ret = [_canned_item()] if attr == "scrape_kenkaku" else (tw_ret if attr == "scrape_twscrape" else None)
        monkeypatch.setattr(collector, attr, _recorder(attr, calls, ret))
    monkeypatch.setattr("kensho.core.notifier.notify_warning", lambda *a, **k: None)

    captured: dict[str, Any] = {}
    real: Callable[..., list[str]] = getattr(collector, "check_dead_sources")

    def _spy(**kw: Any) -> list[str]:
        captured.update(kw)
        return real(**kw)

    monkeypatch.setattr(collector, "check_dead_sources", _spy)

    log = _BufLog()
    collector._collect_impl(_cfg(tmp_path, research_hours), log=log)
    saved = json.loads((tmp_path / "data" / "collected.json").read_text(encoding="utf-8"))
    # calls を検証できるよう返すため保存
    saved["_calls"] = calls
    return log, captured, saved


class TestTwscrapeResearchGating:
    """t_3ecce448: research判定が dead-skip より先で、未試行 run が zero_streak を増やさない"""

    def test_non_research_run_does_not_increment_zero_streak(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """research外run（現行時刻+1h）では z が不変・twscrape は試行もスキップログもされない"""
        _seed_dead_state(tmp_path, 2)
        _non_research = [(datetime.now().hour + 1) % 24]
        log, captured, saved = _run(tmp_path, monkeypatch, _non_research)

        # ① zero_streak が増えていない（sentinel に twscrape が渡されていない）
        state = json.loads((tmp_path / "data" / "dead_source_state.json").read_text(encoding="utf-8"))
        assert state["sources"]["twscrape"]["zero_streak"] == 2
        assert "twscrape" not in captured["by_source"]

        # ② 診断用 collected.json からも "twscrape" キーが消えている（未試行の明示）
        assert "twscrape" not in saved["new_items_by_source"]

        # ③ twscrape は呼ばれない／research分離ログのみ／skipログは出ない
        calls: list[str] = saved["_calls"]
        assert "scrape_twscrape" not in calls
        assert "[RESEARCH分離]" in log.text()
        assert "[TWSCRAPE SKIP]" not in log.text()

        # ④ 成功率メトリクスも汚染されない（試行していない run は runs に載せない）
        health = json.loads((tmp_path / "data" / "source_health.json").read_text(encoding="utf-8"))
        assert health["twscrape_success_rate"]["runs"] == 0

    def test_dead_skip_fires_only_in_research_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """research run で z>=3 → skip は発火し、sentinel には 0 を渡して増分は維持される

        （skip中も z が伸び続けることで DEAD_STREAK_THRESHOLD=12 の [DEAD-SOURCE] アラート
          ＋kanban自動投入が残り、「スキップしたまま無自覚放置」にならない観測経路を保証する）
        """
        _seed_dead_state(tmp_path, 5)
        _research = [datetime.now().hour]
        log, captured, saved = _run(tmp_path, monkeypatch, _research)

        state = json.loads((tmp_path / "data" / "dead_source_state.json").read_text(encoding="utf-8"))
        assert state["sources"]["twscrape"]["zero_streak"] == 6  # 未試行でも research run は増分
        assert captured["by_source"]["twscrape"] == 0
        assert "[TWSCRAPE SKIP] dead-source-state: zero_streak=5>=3" in log.text()
        assert "[RESEARCH分離]" not in log.text()
        calls: list[str] = saved["_calls"]
        assert "scrape_twscrape" not in calls
        assert "twscrape" in saved["new_items_by_source"]  # research run はキー保持
        health = json.loads((tmp_path / "data" / "source_health.json").read_text(encoding="utf-8"))
        assert health["twscrape_success_rate"]["runs"] == 0  # 試行していない run は成功率に載せない

    def test_research_run_attempts_and_counts_zero_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """research run で z<3 → 試行し、0件なら sentinel が z を +1（正常な死検知は維持）"""
        _seed_dead_state(tmp_path, 0)
        _research = [datetime.now().hour]
        log, captured, saved = _run(tmp_path, monkeypatch, _research)

        state = json.loads((tmp_path / "data" / "dead_source_state.json").read_text(encoding="utf-8"))
        assert state["sources"]["twscrape"]["zero_streak"] == 1
        assert captured["by_source"]["twscrape"] == 0
        assert "twscrape" in saved["new_items_by_source"]
        calls: list[str] = saved["_calls"]
        assert "scrape_twscrape" in calls
        assert "[TWSCRAPE SKIP]" not in log.text()
        health = json.loads((tmp_path / "data" / "source_health.json").read_text(encoding="utf-8"))
        assert health["twscrape_success_rate"] == {"runs": 1, "successes": 0, "last": 0.0}

    def test_research_run_with_success_resets_streak_and_counts_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """research run で取得成功 → z=0 リセット・成功率 successes=1（復帰経路の保証）"""
        _seed_dead_state(tmp_path, 2)
        _research = [datetime.now().hour]
        _tw_item = dict(_canned_item())
        _tw_item["source"] = "twscrape"
        _tw_item["x_url"] = "https://x.com/foo/status/222"
        _tw_item["tweet_id"] = "222"
        log, captured, saved = _run(tmp_path, monkeypatch, _research, tw_ret=[_tw_item])

        state = json.loads((tmp_path / "data" / "dead_source_state.json").read_text(encoding="utf-8"))
        assert state["sources"]["twscrape"]["zero_streak"] == 0
        assert captured["by_source"]["twscrape"] == 1
        health = json.loads((tmp_path / "data" / "source_health.json").read_text(encoding="utf-8"))
        assert health["twscrape_success_rate"] == {"runs": 1, "successes": 1, "last": 1.0}
