"""Tests for scripts/agent_eval_harness.py — AI team 3-layer eval harness.

Layers (IBM AI Agent Testing ADLC adapted to critic→worker→QA handoff):
  component : loop_health JSON / evidence.json / notepad / kanban sync payload
  trace     : handoff completeness / game-of-telephone / state transition / dependency gate
  sim       : mock-CLI consecutive-3-run / state persistence / real-board isolation

Each layer has >=3 test cases (total >=9) as required by t_9271d891.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_HARNESS_PATH = Path(__file__).resolve().parent.parent / "scripts" / "agent_eval_harness.py"
_spec = importlib.util.spec_from_file_location("agent_eval_harness", _HARNESS_PATH)
_harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_harness)
sys.modules["agent_eval_harness"] = _harness

from agent_eval_harness import (  # noqa: E402
    _expect,
    judge_dependency_gate,
    judge_evidence_json,
    judge_handoff_complete,
    judge_kanban_sync_payload,
    judge_loop_health_json,
    judge_notepad,
    judge_signal_dropped,
    judge_sim_three_consecutive,
    judge_state_persistence,
    judge_state_transition,
    run_dry_run,
)

LAYERS = ("component", "trace", "sim")


# ─── L1: 構成要素層 ──────────────────────────────────────────────────────────

def _valid_loop_health(score: int = 88) -> str:
    return json.dumps({"score": score, "streak": 0, "running": 2,
                       "blocked": 1, "top_task": None, "lines": ["score=88"]})


@pytest.mark.parametrize("raw, expect_ok", [
    pytest.param(_valid_loop_health(), True, id="valid_loop_health"),
    pytest.param(json.dumps({"score": 150}), False, id="score_out_of_range"),
    pytest.param("not json {", False, id="unparseable"),
], ids=["component_loop_health_normal", "component_loop_health_abnormal_score",
        "component_loop_health_abnormal_parse"])
def test_component_loop_health(raw: str, expect_ok: bool) -> None:
    j = _expect(judge_loop_health_json(raw), expect_ok)
    assert j["correct_execution"] is True
    assert j["layer"] == "component"


def _valid_evidence() -> str:
    return json.dumps({"task_id": "t_sim001", "status": "complete",
                       "success_indicators": ["pytest passes"],
                       "verification_commands": ["$ pytest -q => 3 passed"],
                       "artifact_paths": ["/tmp/artifact1.txt"],
                       "evidence_hashes": ["abc123"]})


@pytest.mark.parametrize("raw, expect_ok", [
    pytest.param(_valid_evidence(), True, id="valid_evidence"),
    pytest.param(json.dumps({"task_id": "t_x"}), False, id="missing_fields"),
    pytest.param(json.dumps({"task_id": "t_x", "status": "complete",
                             "success_indicators": [], "verification_commands": [],
                             "artifact_paths": [], "evidence_hashes": []}),
                 False, id="empty_lists_are_missing"),
], ids=["component_evidence_normal", "component_evidence_abnormal_missing",
        "component_evidence_abnormal_empty"])
def test_component_evidence(raw: str, expect_ok: bool) -> None:
    j = _expect(judge_evidence_json(raw), expect_ok)
    assert j["correct_execution"] is True
    assert j["layer"] == "component"


@pytest.mark.parametrize("text, expect_ok", [
    pytest.param("2026-09-20: lesson one\n2026-09-20: lesson two\n2026-09-20: lesson three\n",
                 True, id="valid_notepad"),
    pytest.param("nodate line\n", False, id="missing_date_prefix"),
    pytest.param("2026-09-20: " + "x" * 300 + "\n", False, id="entry_over_200_chars"),
], ids=["component_notepad_normal", "component_notepad_abnormal_nodate",
        "component_notepad_abnormal_overlong"])
def test_component_notepad(text: str, expect_ok: bool) -> None:
    j = _expect(judge_notepad(text), expect_ok)
    assert j["correct_execution"] is True
    assert j["layer"] == "component"


@pytest.mark.parametrize("payload, expect_ok", [
    pytest.param("worker run: implementation started, 3 files changed", True, id="ascii_payload"),
    pytest.param("worker run: 実装開始 日本語ペイロード", False, id="cjk_payload_rejected"),
], ids=["component_sync_payload_normal", "component_sync_payload_abnormal_cjk"])
def test_component_sync_payload(payload: str, expect_ok: bool) -> None:
    """kanban同期補助ペイロードは tirith confusable ゲート対策で ASCII 限定."""
    j = _expect(judge_kanban_sync_payload(payload), expect_ok)
    assert j["correct_execution"] is True
    assert j["layer"] == "component"


# ─── L2: 軌跡層 ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sig, evidence, status_ok, expect_ok", [
    pytest.param(True, True, True, True, id="complete_handoff_normal"),
    pytest.param(True, False, True, False, id="missing_evidence_abnormal"),
    pytest.param(True, True, False, False, id="bad_status_abnormal"),
], ids=["trace_handoff_normal", "trace_handoff_abnormal_noevidence",
        "trace_handoff_abnormal_badstatus"])
def test_trace_handoff_complete(sig: bool, evidence: bool, status_ok: bool, expect_ok: bool) -> None:
    j = _expect(judge_handoff_complete(sig, evidence, status_ok, ["in_progress", "qa_passed", "done"]), expect_ok)
    assert j["correct_execution"] is True
    assert j["layer"] == "trace"


@pytest.mark.parametrize("sig, evidence, expect_ok", [
    pytest.param(True, True, True, id="signal_persists"),
    pytest.param(True, False, False, id="signal_dropped_abnormal"),
], ids=["trace_signal_persist_normal", "trace_signal_dropped_abnormal"])
def test_trace_signal_dropped(sig: bool, evidence: bool, expect_ok: bool) -> None:
    j = _expect(judge_signal_dropped(sig, evidence), expect_ok)
    assert j["correct_execution"] is True
    assert j["layer"] == "trace"


@pytest.mark.parametrize("seq, expect_ok", [
    pytest.param(["ready", "in_progress", "ready_for_qa", "qa_passed", "done"], True, id="valid_flow"),
    pytest.param(["ready", "in_progress", "qa_failed", "in_progress", "qa_passed", "done"], True, id="valid_with_rework"),
    pytest.param(["blocked", "done"], False, id="illegal_blocked_to_done"),
    pytest.param(["done", "in_progress"], False, id="rewind_done"),
], ids=["trace_transition_valid_flow", "trace_transition_valid_rework",
        "trace_transition_abnormal_blocked_done", "trace_transition_abnormal_rewind"])
def test_trace_state_transition(seq: list[str], expect_ok: bool) -> None:
    j = _expect(judge_state_transition(seq), expect_ok)
    assert j["correct_execution"] is True
    assert j["layer"] == "trace"


@pytest.mark.parametrize("parent_done, child_state, expect_ok", [
    pytest.param(True, "done", True, id="parent_done_child_done_ok"),
    pytest.param(False, "done", False, id="child_done_before_parent_abnormal"),
    pytest.param(False, "in_progress", True, id="child_still_working_ok"),
], ids=["trace_depgate_normal", "trace_depgate_abnormal_backchain",
        "trace_depgate_normal_working"])
def test_trace_dependency_gate(parent_done: bool, child_state: str, expect_ok: bool) -> None:
    j = _expect(judge_dependency_gate(parent_done, child_state), expect_ok)
    assert j["correct_execution"] is True
    assert j["layer"] == "trace"


# ─── L3: 疑似本番層 ──────────────────────────────────────────────────────────

def test_sim_three_consecutive(tmp_path: Path) -> None:
    """cron相当の連続3実行が全run成功(成功判定率100%)する."""
    j = judge_sim_three_consecutive(tmp_path)
    assert j["ok"] is True
    assert j["layer"] == "sim"
    # 3つの run 成果物が一時dirに生成されている(モックCLI=本番API未使用)
    assert len(list(tmp_path.glob("evidence*.json"))) == 3
    assert len(list(tmp_path.glob("artifact*.txt"))) == 3


def test_sim_state_persistence(tmp_path: Path) -> None:
    """連続3実行後も loop_state.json が構造有効(破損なし)."""
    j = judge_state_persistence(tmp_path)
    assert j["ok"] is True
    assert j["layer"] == "sim"
    state = json.loads((tmp_path / "loop_state.json").read_text(encoding="utf-8"))
    assert "score" in state and "streak" in state and "run" in state


def test_sim_state_file_shared_across_runs(tmp_path: Path) -> None:
    """3連続実行が同一の loop_state.json を共有(実機のstreak状態ファイル相当)."""
    from agent_eval_harness import simulate_cron_run
    for i in range(3):
        simulate_cron_run(tmp_path, i)
        assert (tmp_path / "loop_state.json").exists()
    # 単一の共有stateのみ存在し、runごとに複製されないこと
    assert len(list(tmp_path.glob("loop_state.json"))) == 1


def test_sim_isolation_no_real_board_write(tmp_path: Path) -> None:
    """本番Kanban/notepad前後で件数・値が一致(本番変更0件)."""
    from agent_eval_harness import _snapshot_board_counts, _snapshot_notepad
    before = {"counts": _snapshot_board_counts().get("counts"),
              "notepad": _snapshot_notepad()}
    # L3 疑似実行(一時dir・本番API非接触)
    judge_sim_three_consecutive(tmp_path)
    judge_state_persistence(tmp_path)
    after = {"counts": _snapshot_board_counts().get("counts"),
             "notepad": _snapshot_notepad()}
    assert before == after


# ─── 層カバレッジ: 各層>=3、合計>=9 ─────────────────────────────────────────

def test_layer_coverage_meta() -> None:
    """dry-run全シナリオが各層3件以上・合計9件以上の判定を収録している."""
    judgements = run_dry_run(serialize=True)
    layercount = {layer: sum(1 for j in judgements if j["layer"] == layer)
                  for layer in LAYERS}
    assert all(layercount[layer] >= 3 for layer in LAYERS)
    assert len(judgements) >= 9
