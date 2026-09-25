"""Tests for scripts/outcome_review_check.py — 事後効果測定の定期再確認（t_eca89f41）

ネットワーク不使用。tmp_path 上に kanban DB と reports/ を作り、
判定（pass/missing/na）・集計（実測確認率）・critic注入markdown・CLI終了コードを検証する。
判定規則が doneガード条件(k) と乖離していないことを検証するドリフトテストも含む。
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import outcome_review_check as mod

GUARD_PATH = Path.home() / ".hermes" / "profiles" / "kensho-sweeps" / "scripts" / "kanban_done_guard.py"


def _make_db(path: Path, tasks: list[tuple[str, str, str, int]]) -> Path:
    """tasks(id, title, assignee, completed_at) だけ持つ最小DBを作る。"""
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE tasks (id TEXT, title TEXT, assignee TEXT, status TEXT, "
        "completed_at INTEGER, result TEXT)"
    )
    for tid, title, assignee, ts in tasks:
        con.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?)", (tid, title, assignee, "done", ts, "ok")
        )
    con.commit()
    con.close()
    return path


def _write_evidence(reports: Path, tid: str, data: dict[str, object]) -> Path:
    p = reports / f"{tid}_evidence.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# --- classify（判定規則） ---------------------------------------------------


def test_classify_pass_with_outcome_field() -> None:
    data = {
        "success_indicators": ["RT成功率 40%"],
        "outcome": {"metric": "RT成功率", "before": 12, "after": 30},
    }
    st = mod.classify("", data)
    assert st["status"] == "pass"
    assert st["outcome_ok"] is True


def test_classify_pass_with_markdown_metrics() -> None:
    st = mod.classify("# verification_evidence\nbefore=12% → after=30%\n", {"success_indicators": ["RT成功率 40%"]})
    assert st["status"] == "pass"
    assert st["md_hits"]


def test_classify_missing_when_numeric_kpi_without_metrics() -> None:
    st = mod.classify("", {"success_indicators": ["エラー率を5%以下に"]})
    assert st["status"] == "missing"


def test_classify_na_when_no_numeric_kpi() -> None:
    st = mod.classify("", {"success_indicators": ["ドキュメントを整備する"]})
    assert st["status"] == "na"


def test_classify_incomplete_outcome_is_missing() -> None:
    data = {"success_indicators": ["応募成功率 30%"], "outcome": {"metric": "応募成功率", "before": 10}}
    st = mod.classify("", data)
    assert st["status"] == "missing"


def test_regressions_detects_after_lower_than_before() -> None:
    entries = [
        {"metric": "A", "before": 10, "after": 5},
        {"metric": "B", "before": 5, "after": 10},
    ]
    assert [e["metric"] for e in mod.regressions(entries)] == ["A"]


def test_regressions_excludes_direction_undeclared_when_metric_is_down_is_better() -> None:
    """Test that direction undeclared entries with lower-is-better metrics are excluded from regressions."""
    entries = [
        {"metric": "失敗回数", "before": 10, "after": 5},  # lower is better, after < before = improvement
        {"metric": "成功率", "before": 5, "after": 10},   # higher is better, after > before = improvement
    ]
    regressed = mod.regressions(entries)
    assert len(regressed) == 0


def test_regressions_includes_when_direction_declared_and_worsens() -> None:
    """Test that direction declared entries that worsen are included in regressions."""
    entries = [
        {"metric": "失敗回数", "before": 10, "after": 15, "direction": "down"},  # lower is better, after > before = worsening
        {"metric": "成功率", "before": 5, "after": 3, "direction": "up"},     # higher is better, after < before = worsening
    ]
    regressed = mod.regressions(entries)
    assert len(regressed) == 2
    assert {e["metric"] for e in regressed} == {"失敗回数", "成功率"}


def test_regressions_auto_direction_from_metric() -> None:
    """Test auto direction detection from metric names."""
    entries = [
        {"metric": "失敗回数", "before": 10, "after": 15},  # lower is better, after > before
        {"metric": "成功率", "before": 5, "after": 3},   # higher is better, after < before
        {"metric": "総件数", "before": 10, "after": 5},  # unknown direction, should be undeclared
    ]
    regressed = mod.regressions(entries)
    # Should include only the first two (auto-detected directions that worsen)
    assert len(regressed) == 2
    assert {e["metric"] for e in regressed} == {"失敗回数", "成功率"}


def test_direction_label_reports_numeric_movement_not_quality() -> None:
    assert mod.direction_label(10, 5) == "方向: down"
    assert mod.direction_label(5, 10) == "方向: up"
    assert mod.direction_label(3, 3) == "方向: equal"
    assert mod.direction_label("5/6 PASS", "6/6 PASS") is None


def test_render_markdown_adds_direction_to_every_outcome_entry() -> None:
    summary = {
        "days": 7,
        "since": "2026-09-17",
        "counts": {"done": 1, "measured": 1, "missing": 0, "na": 0, "numeric_kpi_tasks": 1, "regressed": 1},
        "measured_rate": 100.0,
        "target_rate": 50.0,
        "target_met": True,
        "measured": [
            {
                "id": "t_ok",
                "outcome": [
                    {"metric": "latency", "before": 10, "after": 5},
                    {"metric": "throughput", "before": 5, "after": 10},
                    {"metric": "unchanged", "before": 3, "after": 3},
                ],
            }
        ],
        "missing": [],
        "regressions": [{"id": "t_ok", "regressions": [{"metric": "latency", "before": 10, "after": 5}]}],
        "tasks": [],
    }

    md = mod.render_markdown(summary)
    measured_line = next(line for line in md.splitlines() if "`t_ok`" in line and "latency" in line)
    regression_line = next(line for line in md.splitlines() if "悪化疑い" not in line and line.endswith("10→5 (方向: down)"))

    assert measured_line.count("方向:") == 3
    assert "方向: down" in measured_line
    assert "方向: up" in measured_line
    assert "方向: equal" in measured_line
    assert regression_line == "  - `t_ok` latency 10→5 (方向: down)"


def test_render_markdown_states_direction_rule() -> None:
    """方向ラベルの意味（上下のみ・良悪は指標依存）がレポート本文に明文化されていること。"""
    summary = {
        "days": 7,
        "since": "2026-09-17",
        "counts": {"done": 0, "measured": 0, "missing": 0, "na": 0, "numeric_kpi_tasks": 0, "regressed": 0},
        "measured_rate": None,
        "target_rate": 50.0,
        "target_met": False,
        "measured": [],
        "missing": [],
        "regressions": [],
        "tasks": [],
    }

    md = mod.render_markdown(summary)
    rule_line = next(line for line in md.splitlines() if "KPI方向性ルール" in line)

    assert "方向: up/down/equal" in rule_line
    assert "数値の上下のみ" in rule_line
    assert "良悪" in rule_line


# --- audit / summarize / render --------------------------------------------


def test_audit_task_end_to_end(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    _write_evidence(
        reports,
        "t_ok",
        {"success_indicators": ["成功率 80%"], "outcome": {"metric": "成功率", "before": 40, "after": 80}},
    )
    (reports / "t_missing_verification.md").write_text("# verification_evidence\n", encoding="utf-8")
    _write_evidence(reports, "t_missing", {"success_indicators": ["成功率 80%"]})

    task = {"id": "t_missing", "title": "未実測タスク", "assignee": "w", "completed_date": "2026-09-23"}
    rec = mod.audit_task(task, reports)
    assert rec["status"] == "missing"
    assert rec["evidence_path"] is not None

    task_ok = {"id": "t_ok", "title": "実測済み", "assignee": "w", "completed_date": "2026-09-23"}
    rec_ok = mod.audit_task(task_ok, reports)
    assert rec_ok["status"] == "pass"
    assert rec_ok["outcome"][0]["after"] == 80


def test_summarize_rate_and_target(tmp_path: Path) -> None:
    records: list[dict[str, object]] = [
        {"id": "a", "title": "a", "assignee": "w", "completed_date": "d", "status": "pass",
         "outcome": [], "regressions": [], "evidence_path": None, "verification_path": None, "note": ""},
        {"id": "b", "title": "b", "assignee": "w", "completed_date": "d", "status": "missing",
         "outcome": [], "regressions": [], "evidence_path": None, "verification_path": None, "note": ""},
        {"id": "c", "title": "c", "assignee": "w", "completed_date": "d", "status": "na",
         "outcome": [], "regressions": [], "evidence_path": None, "verification_path": None, "note": ""},
    ]
    s = mod.summarize(records, 7, "2026-09-16")
    assert s["counts"]["numeric_kpi_tasks"] == 2
    assert s["measured_rate"] == 50.0
    assert s["target_met"] is True
    md = mod.render_markdown(s)
    assert "事後効果測定" in md and "50.0%" in md


# --- CLI --------------------------------------------------------------------


def test_cli_json_and_strict_exit(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    _write_evidence(reports, "t_ng", {"success_indicators": ["成功率 80%"]})
    import time

    db = _make_db(tmp_path / "kanban.db", [("t_ng", "未実測", "w", int(time.time()))])

    assert mod.main(["--db", str(db), "--reports-dir", str(reports), "--json"]) == 0
    assert mod.main(["--db", str(db), "--reports-dir", str(reports), "--strict"]) == 1
    assert mod.main(["--db", str(tmp_path / "nope.db"), "--reports-dir", str(reports)]) == 3


def test_cli_write_report(tmp_path: Path) -> None:
    import time

    reports = tmp_path / "reports"
    reports.mkdir()
    _write_evidence(
        reports,
        "t_ok",
        {"success_indicators": ["成功率 80%"], "outcome": {"metric": "成功率", "before": 40, "after": 80}},
    )
    db = _make_db(tmp_path / "kanban.db", [("t_ok", "実測済み", "w", int(time.time()))])
    assert mod.main(["--db", str(db), "--reports-dir", str(reports), "--write-report"]) == 0
    report = next(reports.glob("outcome-review-*.md"))
    assert "方向:" in report.read_text(encoding="utf-8")


# --- ドリフト検出（ガード条件(k) と同一規則であること） ----------------------


@pytest.mark.skipif(not GUARD_PATH.is_file(), reason="doneガード未配置（CI等）")
def test_no_drift_with_done_guard_condition_k() -> None:
    spec = importlib.util.spec_from_file_location("_done_guard_for_test", GUARD_PATH)
    assert spec is not None and spec.loader is not None
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)

    fixtures: list[tuple[str, dict[str, object]]] = [
        ("", {"success_indicators": ["成功率 80%"], "outcome": {"metric": "成功率", "before": 1, "after": 2}}),
        ("before=12% → after=30%", {"success_indicators": ["成功率 80%"]}),
        ("", {"success_indicators": ["成功率 80%"]}),
        ("", {"success_indicators": ["整備する"]}),
        ("", {"success_indicators": ["成功率 80%"], "outcome": {"metric": "m", "before": "x", "after": "y"}}),
    ]
    # ガードは gating 用に fail/skip の語を使うが、意味は missing/na と同一。
    guard_to_local = {"pass": "pass", "fail": "missing", "skip": "na"}
    for text, data in fixtures:
        expected = guard_to_local[str(guard.outcome_review_state(text, data)["status"])]
        assert mod.classify(text, data)["status"] == expected, (text, data)
