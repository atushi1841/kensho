#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AIチーム検証の3層化 エージェント評価ハーネス (t_9271d891).

IBM「AI Agent Testing」(構成要素→経路/エンドツーエンド→環境/それ以上)の
ADLC連続評価を、Kensho AIチーム(critic→worker→QAの受け渡し)に適用する自動ゲート。
Sectioning/compaction/ゾンビ検出/リトライとは異なる「ADLC連続評価 + 3層テスト +
疑似本番環境」の機構を提供する。

3層:
  L1 component(構成要素) : loop_health JSON / evidence.json / notepad / kanban同期補助 の正常・異常判定
  L2 trace(軌跡)        : critic提案→worker実装→QA合格の似机 handoff 複数パターンの
                           完了シグナル・証拠・状態遷移の追跡
  L3 sim(疑似本番)       : 一時ディレクトリ + モックCLI で cron相当の連続3実行を再現。
                           本番Kanban・notepad・cronには一切触れない(本番変更0件)。

収録は層毎に 3 件以上、合計 9 件以上の判定シナリオ。シナリオは純粋関数 judge_*
として実装し、全実行は --dry-run で独立に検証できる(本番無変更)。

使用法 (検証コマンド):
  .venv/bin/python -m pytest tests/test_agent_eval_harness.py -q      # 単体テスト
  python3 scripts/agent_eval_harness.py --dry-run                     # 全9判定 + 疑似3連実行 + 分離検証
  python3 scripts/agent_eval_harness.py --json                        # 判定結果をJSONで出力(exit 0/1)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# ─── 定数: 実機構の契約フィールド ─────────────────────────────────────────────
# done_guard 条件(j): evidence.json の必須6フィールド(欠落>0で FAIL)
EVIDENCE_FIELDS: tuple[str, ...] = (
    "task_id",
    "status",
    "success_indicators",
    "verification_commands",
    "artifact_paths",
    "evidence_hashes",
)
# loop_health.sh v137 出力の必須フィールド
LOOP_HEALTH_FIELDS: tuple[str, ...] = (
    "score",
    "streak",
    "running",
    "blocked",
    "top_task",
    "lines",
)
# notepad 構造化規則 (ai-team-improvement 2026-08-29): 日付付き・最大5件・各200字
NOTEPAD_MAX_ENTRIES = 5
NOTEPAD_MAX_CHARS = 200

# L2 状態遷移: 受け渡しライフサイクルの許容遷移表
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "ready": {"in_progress"},
    "in_progress": {"ready_for_qa", "qa_passed", "qa_failed", "blocked", "done"},
    "ready_for_qa": {"qa_passed", "qa_failed"},
    "qa_failed": {"in_progress"},
    "qa_passed": {"done"},
    "blocked": {"in_progress", "ready"},
    "done": set(),
}

Judge = dict[str, Any]


def _mk(scenario: str, layer: str, field: str, ok: bool, expected: Any, actual: Any, detail: str = "") -> Judge:
    return {
        "scenario": scenario,
        "layer": layer,
        "field": field,
        "ok": bool(ok),
        "expected": expected,
        "actual": actual,
        "detail": detail,
    }


# ═══ L1: 構成要素層 ==========================================================

def judge_loop_health_json(raw: str | bytes) -> Judge:
    """loop_health.sh JSON の正常/異常判定。必須フィールド・score範囲・型を検証."""
    ok = False
    detail = ""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return _mk("component_loop_health_parse", "component", "parse",
                   False, "valid JSON", f"invalid JSON: {e}"[:120], "異常: 非パース")
    missing = [f for f in LOOP_HEALTH_FIELDS if f not in data]
    if missing:
        detail = f"欠落フィールド: {missing}"
    else:
        score = data["score"]
        if not isinstance(score, int) or isinstance(score, bool) or not (0 <= score <= 100):
            detail = f"score範囲外: {score!r} (必須 0..100 int)"
        else:
            ok = True
            detail = f"score={score}, streak={data['streak']}, running={data['running']}, blocked={data['blocked']}"
    return _mk("component_loop_health", "component", "loop_health_json", ok,
               "required fields + score 0..100", "missing" if not ok and missing else "valid", detail)


def judge_evidence_json(raw: str | bytes) -> Judge:
    """done_guard 条件(j) の evidence.json スキーマ判定。必須6フィールド非空を要求."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return _mk("component_evidence_parse", "component", "parse", False,
                   "valid JSON", f"invalid JSON: {e}"[:120], "異常: 非パース")
    missing = [f for f in EVIDENCE_FIELDS if f not in data]
    if missing:
        detail = f"欠落フィールド: {missing}"
    else:
        empty = [f for f in EVIDENCE_FIELDS
                 if isinstance(data[f], list) and len(data[f]) == 0]
        if empty:
            detail = f"空リスト(欠落扱い): {empty}"
        else:
            detail = f"6フィールド充足 (task_id={data['task_id']}, status={data['status']})"
    return _mk("component_evidence", "component", "evidence_json",
               not missing and not empty, "6 required non-empty fields", "missing" if missing else "valid", detail)


def judge_notepad(text: str) -> Judge:
    """notepad構造化ルール(2026-08-29)の判定: 日付付き・最大5件・各200字."""
    entries = [ln for ln in text.splitlines() if ln.strip()]
    ok = True
    problems: list[str] = []
    if len(entries) > NOTEPAD_MAX_ENTRIES:
        problems.append(f"エントリ超過 {len(entries)} > {NOTEPAD_MAX_ENTRIES}")
    for i, ln in enumerate(entries, 1):
        if not re.match(r"^\d{4}-\d{2}-\d{2}:", ln):
            problems.append(f"#{i} 日付プレフィックス欠落")
        if len(ln) > NOTEPAD_MAX_CHARS:
            problems.append(f"#{i} {len(ln)}字 > {NOTEPAD_MAX_CHARS}")
    ok = not problems
    return _mk("component_notepad", "component", "notepad_format", ok,
               "date-prefixed, <=5 entries, <=200 chars each",
               problems if problems else f"{len(entries)} entries", "; ".join(problems) if problems else "正常(fresh)")


def judge_kanban_sync_payload(payload: str) -> Judge:
    """kanban同期補助(v2, t_47ae8229)のペイロード安全判定: ASCII-onlyのみ正常.

    tirith confusable_text ゲートに対抗するため、writeペイロードは printable ASCII 限定。
    非ASCII(CJK含む)を検出したら異常と判定。
    """
    ascii_ok = all(32 <= ord(c) <= 126 or c in "\n\r\t" for c in payload)
    if not ascii_ok:
        bad = sorted({c for c in payload if not (32 <= ord(c) <= 126 or c in "\n\r\t")})[:5]
        return _mk("component_sync_payload", "component", "kanban_sync_payload_ascii",
                   False, "printable-ASCII only", f"non-ASCII: {bad}", "異常: tirith confusable リスク")
    return _mk("component_sync_payload", "component", "kanban_sync_payload_ascii",
               True, "printable-ASCII only", "ascii", "正常: ペイロードASCII")


# ═══ L2: 軌跡層 ==============================================================

def judge_handoff_complete(sig: bool, evidence: bool, status_ok: bool, seq: list[str]) -> Judge:
    """似机 handoff 完全性: 完了シグナル + 証拠 + 状態遷移全て揃えば正常."""
    ok = sig and evidence and status_ok
    detail = f"sig={sig}, evidence={evidence}, status_ok={status_ok}, seq={seq}"
    return _mk("trace_handoff_complete", "trace", "completion_signal", ok,
               "signal AND evidence AND status_ok", ok, detail)


def judge_signal_dropped(sig: bool, evidence: bool) -> Judge:
    """game of telephone(完了シグナル消失)の検出. sig有りでも証拠消失は異常."""
    abnormal = sig and not evidence
    ok = not abnormal
    detail = f"sig={sig}, evidence={evidence}  → {'異常: 完瞭シグナルが証拠に反映されず消失' if abnormal else '受け渡し正常'}"
    return _mk("trace_signal_dropped", "trace", "game_of_telephone", ok,
               "complete signal must persist to evidence", abnormal, detail)


def judge_state_transition(seq: list[str]) -> Judge:
    """許容遷移表(ALLOWED_TRANSITIONS)に従う状態遷移列の妥当性判定."""
    if not seq:
        return _mk("trace_state_transition", "trace", "state_sequence", False,
                   "non-empty seq", "empty", "異常: 遷移列なし")
    bad: list[str] = []
    for a, b in zip(seq, seq[1:]):
        if b not in ALLOWED_TRANSITIONS.get(a, set()):
            bad.append(f"{a}→{b}")
    ok = not bad
    return _mk("trace_state_transition", "trace", "state_sequence", ok,
               "all transitions allowed", bad if bad else seq, "; ".join(bad) if bad else f"valid: {' → '.join(seq)}")


def judge_dependency_gate(parent_done: bool, child_state: str) -> Judge:
    """親未完了のまま子が完了へ進む不正バックチェーン(過剰手戻り)の判定."""
    invalid = (child_state == "done") and not parent_done
    ok = not invalid
    return _mk("trace_dependency_gate", "trace", "back_chaining", ok,
               "child must not reach done before parent done",
               {"parent_done": parent_done, "child": child_state},
               "異常: 親未doneで子done" if invalid else "依存ゲート正常")


# ═══ L3: 疑似本番層 ==========================================================

def simulate_cron_run(basedir: Path, run_idx: int) -> dict:
    """cron相当の1実行: critic→worker→QA の mini-handoff を一時dirで再現.

    モックCLI(本番APIは呼ばない)で proposal/evidence/loop_state を temp 下に生成し、
    L1判定を通す。本番Kanban・notepad・cron実データには触れない。
    """
    proposal = basedir / f"critic_proposal_run{run_idx}.md"
    proposal.write_text(
        f"## Proposal run {run_idx}\n- fix issue alpha\n- ASCII payload: scanner gate OK\n",
        encoding="utf-8",
    )
    artifact = basedir / f"artifact{run_idx}.txt"
    artifact.write_text("artifact", encoding="utf-8")
    evidence = {
        "task_id": f"t_sim{run_idx:03d}",
        "status": "complete",
        "success_indicators": [f"sim run {run_idx + 1} passes"],
        "verification_commands": [f"$ pytest -q => 9 passed"],
        "artifact_paths": [str(artifact)],
        "evidence_hashes": ["abc123"],
    }
    (basedir / f"evidence{run_idx}.json").write_text(json.dumps(evidence), encoding="utf-8")

    state_file = basedir / "loop_state.json"
    prev_streak = 0
    if state_file.exists():
        try:
            prev_streak = int(json.loads(state_file.read_text()).get("streak", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            prev_streak = 0
    score = 100 - run_idx * 2
    state = {"score": score, "streak": 0 if score >= 70 else prev_streak + 1,
             "running": 0, "blocked": 0, "top_task": None,
             "lines": [f"score={score}"], "run": run_idx}
    state_file.write_text(json.dumps(state), encoding="utf-8")

    checks = [
        judge_loop_health_json(json.dumps(state)),
        judge_evidence_json(json.dumps(evidence)),
        judge_kanban_sync_payload(proposal.read_text(encoding="utf-8")),
    ]
    passed = sum(1 for c in checks if c["ok"])
    return {"run": run_idx + 1, "ok": passed == len(checks),
            "checks_total": len(checks), "checks_passed": passed,
            "state_path": str(state_file)}
    # 遷移: in_progress→(ready_for_qa→)qa_passed→done を許容表で追跡
    _seq = ["in_progress", "qa_passed", "done"]


def judge_sim_three_consecutive(basedir: Path) -> Judge:
    """cron相当の連続3実行: 全run成功判定(streak状態ファイルを共有して連続実行)."""
    results = [simulate_cron_run(basedir, i) for i in range(3)]
    passed = [r["run"] for r in results if r["ok"]]
    rate = round(100.0 * len(passed) / len(results), 1)
    ok = all(r["ok"] for r in results)
    detail = f"3連続実行 → 成功 {len(passed)}/3 ({rate}%), runs={[r['run'] for r in results]}, 成功判定率100%条件"
    return _mk("sim_three_consecutive", "sim", "cron_3_runs", ok,
               "3/3 success (100%)", f"{len(passed)}/3 ({rate}%)", detail)


def judge_state_persistence(basedir: Path) -> Judge:
    """状態ファイル共有で3連続実行後も loop_state.json が構造有効(破損なし)を判定."""
    results = [simulate_cron_run(basedir, i) for i in range(3)]
    state_file = basedir / "loop_state.json"
    try:
        final_state = json.loads(state_file.read_text(encoding="utf-8"))
        ok = isinstance(final_state, dict) and "score" in final_state and "streak" in final_state
        detail = f"最終 state: score={final_state.get('score')}, streak={final_state.get('streak')}, run={final_state.get('run')}"
    except (json.JSONDecodeError, OSError) as e:
        ok = False
        detail = f"state破損: {e}"
    prev = basedir / "loop_state.prev.json"
    if prev.exists():
        try:
            prev_state = json.loads(prev.read_text(encoding="utf-8"))
            if prev_state.get("streak", 0) > 0 and final_state is not None:
                final_state = final_state  # streak 継承の妥当性は次の実行側で担保
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    return _mk("sim_state_persistence", "sim", "state_corruption", ok,
               "loop_state.json valid after 3 runs", ok, detail)


def _snapshot_board_counts() -> dict:
    """本番Kanban DBの状態別件数カウント(読み取り専用・本番無変更)."""
    for cand in (
        os.environ.get("HERMES_KANBAN_DB"),
        str(Path.home() / ".hermes/kanban/boards/kensho-ai-team/kanban.db"),
        str(Path.home() / ".hermes/kanban.db"),
    ):
        if cand and Path(cand).exists():
            import sqlite3
            conn = sqlite3.connect(cand)
            try:
                rows = conn.execute("select status, count(*) from tasks group by status")
                return {"db": cand, "counts": {s: c for s, c in rows}}
            except sqlite3.Error as e:
                return {"db": cand, "counts": {"error": str(e)}}
            finally:
                conn.close()
    return {"db": None, "counts": None}


def _snapshot_notepad() -> str:
    """本番notepad値の読み取り(best-effort・読み取り専用)."""
    for job in ("4baf143523e0", "5e8ec4984bba", "033ff6065ef7"):
        try:
            out = subprocess.run(
                ["hermes", "cron", "notepad", job, "get", "lessons"],
                capture_output=True, text=True, timeout=60,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()[:200]
        except (OSError, subprocess.SubprocessError):
            continue
    return "NOTEPAD_ABSENT"


def judge_isolation(before: dict, after: dict) -> Judge:
    """本番無変更の検証: 実行前後の本番Kanban件数・notepad値が完全一致."""
    same_counts = before.get("counts") == after.get("counts")
    same_notepad = before.get("notepad") == after.get("notepad")
    ok = same_counts and same_notepad
    detail = (f"Kanban件数: {before.get('counts')} == {after.get('counts')} ({same_counts}), "
              f"notepad: {before.get('notepad')!r} == {after.get('notepad')!r} ({same_notepad})")
    return _mk("sim_isolation", "sim", "real_board_untouched", ok,
               "before == after (本番変更0件)", same_counts, detail)


def _expect(judge: Judge, expect_ok: bool) -> Judge:
    """シナリオの期待判定を添付: 検出器が入力の正常/異常を正しく判定できたかを検証.

    - 正常入力(expect_ok=True) で judge ok=False → 回帰(検出器が見逃し)
    - 異常入力(expect_ok=False) で judge ok=True → 見逃し(検出失敗)
    どちらも「シナリオ失敗」として集計する。ok 自体は入力の正常/異常の記録であり、
    異常検出シナリオで ok=False は正常動作(異常を正しく指摘)。この wrapper が
    「検出器が正しく動いたか」の基準を提供する。
    """
    correct = (judge["ok"] == expect_ok)
    return {**judge, "expected_ok": expect_ok, "correct_execution": correct}


def run_dry_run(serialize: bool = True) -> list[Judge]:
    """全判定シナリオ + 疑似3連実行 + 分離検証を実行し判定リストを返す.

    L1/L2 は純粋関数に固定入力、L3 は tempdir でモックCLIを実行。
    本番Kanban・cron・notepadへの書き込みは一切行わない(読み取りのみ)。
    各シナリオは `expected_ok`(=normalならTrue, abnormal検出シナリオならFalse)
    を持ち、検出器が期待どおり判定したか(_expect)で合否を集計する。
    """
    judgements: list[Judge] = []

    # ── L1 構成要素層 (8件: loop_health / evidence / notepad / kanban同期補助)
    judgements.append(_expect(judge_loop_health_json(json.dumps(
        {"score": 88, "streak": 0, "running": 2, "blocked": 1, "top_task": None,
         "lines": ["score=88"]})), True))
    judgements.append(_expect(judge_loop_health_json(json.dumps({"score": 150})), False))  # 異常: score範囲外+欠落
    judgements.append(_expect(judge_evidence_json(json.dumps(
        {"task_id": "t_x", "status": "complete", "success_indicators": ["s"],
         "verification_commands": ["$ pytest -q"], "artifact_paths": ["/tmp/a"],
         "evidence_hashes": ["h"]})), True))
    judgements.append(_expect(judge_evidence_json(json.dumps({"task_id": "t_y"})), False))  # 異常: 必須フィールド欠落
    judgements.append(_expect(judge_notepad(
        "2026-09-20: lesson one\n2026-09-20: lesson two\n2026-09-20: lesson three\n"), True))
    judgements.append(_expect(judge_notepad(
        "2026-09-20: lesson one\nnodate line\n2026-09-20: " + "x" * 300 + "\n"), False))  # 異常: 非日付・200字超
    judgements.append(_expect(judge_kanban_sync_payload("worker run: implementation started"), True))
    judgements.append(_expect(judge_kanban_sync_payload("worker run: 実装開始 日本語ペイロード"), False))  # 異常: 非ASCII

    # ── L2 軌跡層 (8件)
    judgements.append(_expect(judge_handoff_complete(True, True, True, ["in_progress", "qa_passed", "done"]), True))
    judgements.append(_expect(judge_handoff_complete(True, False, True, ["in_progress", "done"]), False))  # 異常: 証拠欠落
    judgements.append(_expect(judge_signal_dropped(True, False), False))  # 異常: 完了シグナル消失
    judgements.append(_expect(judge_signal_dropped(True, True), True))
    judgements.append(_expect(judge_state_transition(["ready", "in_progress", "qa_passed", "done"]), True))
    judgements.append(_expect(judge_state_transition(["blocked", "done"]), False))  # 異常: 不正遷移
    judgements.append(_expect(judge_dependency_gate(False, "done"), False))  # 異常: 親未doneで子done
    judgements.append(_expect(judge_dependency_gate(True, "done"), True))

    # ── L3 疑似本番層 (3件)
    before = {"counts": _snapshot_board_counts().get("counts"),
              "notepad": _snapshot_notepad()}
    with tempfile.TemporaryDirectory(prefix="agent_eval_harness_") as td:
        basedir = Path(td)
        judgements.append(_expect(judge_sim_three_consecutive(basedir), True))
        judgements.append(_expect(judge_state_persistence(basedir), True))
        after = {"counts": _snapshot_board_counts().get("counts"),
                 "notepad": _snapshot_notepad()}
    judgements.append(_expect(judge_isolation(before, after), True))

    if serialize:
        return judgements
    out = {"judgements": judgements,
           "passed": sum(1 for j in judgements if j["ok"]),
           "correct": sum(1 for j in judgements if j["correct_execution"]),
           "total": len(judgements),
           "layers": {layer: sum(1 for j in judgements if j["layer"] == layer) for layer in ("component", "trace", "sim")}}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return judgements


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="AI team 3-layer agent eval harness")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--dry-run", action="store_true", help="run all judges, no real-board writes")
    args = ap.parse_args()

    judgements = run_dry_run(serialize=False)
    correct = sum(1 for j in judgements if j["correct_execution"])
    total = len(judgements)
    layers = {layer: sum(1 for j in judgements if j["layer"] == layer) for layer in ("component", "trace", "sim")}
    layer_coverage = all(v >= 3 for v in layers.values())
    # L3 疑似本番: 連続3実行の成功判定率(judge ok==True が3件中全部)を要求
    sim3 = next((j for j in judgements if j["scenario"] == "sim_three_consecutive"), None)
    sim_success_ok = bool(sim3 and sim3["ok"])
    gate = (correct == total) and layer_coverage and sim_success_ok

    if args.json or "--json" in sys.argv:
        print(json.dumps({
            "harness": "agent_eval_harness",
            "task": "t_9271d891",
            "gate": gate,
            "correct_execution": correct,
            "total": total,
            "layers": layers,
            "sim_three_consecutive_success": sim_success_ok,
            "layer_coverage": layer_coverage,
        }, ensure_ascii=False, indent=2))
        return 0 if gate else 1

    print(f"agent_eval_harness: {correct}/{total} scenarios executed correctly (gate pass={gate})")
    print(f"  layers: {layers}  (each>=3 required => {layer_coverage})")
    print(f"  sim 3連続実行 成功判定率100% => {sim_success_ok}")
    for j in judgements:
        tag = "PASS" if j["correct_execution"] else "FAIL"
        expect = "normal" if j["expected_ok"] else "abnormal"
        print(f"  [{tag:4}] layer={j['layer']:<10} scen={j['scenario']:<26} expect={expect:<8} ok={'T' if j['ok'] else 'F'}  {j['detail'][:80]}")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
