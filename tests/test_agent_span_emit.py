"""tests/test_agent_span_emit.py — エージェント実行テレメトリの回帰テスト (t_8158cb49).

対象: OTel GenAI semconv 準拠の span JSONL emit（scripts/agent_span_emit.py）と
agent別集計（scripts/agent_span_report.py）。

観点:
  1. 必須フィールドが全存在し、成功時は error.type を持たない
  2. 追記が非破壊（既存行はバイト単位で不変・1実行=1行）
  3. 壊れた行・欠落行はスキップし、集計値を歪めない（警告のみ）
  4. agent別の 実行数/成功率/平均duration/token合計/エラー内訳 が正しい
  5. cron 安全（ファイル不在・空ファイル・不正値でも exit 0）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import agent_span_emit as emit  # noqa: E402
import agent_span_report as report  # noqa: E402

#: タスク仕様の必須フィールド（error.type は失敗時のみ）
SPEC_FIELDS = (
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.agent.name",
    "gen_ai.request.model",
    "gen_ai.conversation.id",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "duration_ms",
)

DAY = "2026-09-23"


def _run(script: str, args: list[str], out_dir: Path) -> subprocess.CompletedProcess[str]:
    """scripts/<script> を subprocess 実行（span 出力先は tmp_path に隔離）."""
    env = {
        **os.environ,
        "KENSHO_AGENT_SPANS_DIR": str(out_dir),
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=120,
    )


# ── 1. 必須フィールド ────────────────────────────────────────────────────────

def test_emitted_line_has_all_required_fields(tmp_path: Path) -> None:
    proc = _run("agent_span_emit.py", [
        "--agent", "kensho-qa", "--model", "deepseek-v4-flash", "--task-id", "t_TEST",
        "--tokens-in", "100", "--tokens-out", "50", "--duration-ms", "1200", "--date", DAY,
    ], tmp_path)
    assert proc.returncode == 0, proc.stderr

    lines = (tmp_path / f"{DAY}.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "1実行=1行であること"
    span = json.loads(lines[0])
    for field in SPEC_FIELDS:
        assert field in span, f"必須フィールド欠落: {field}"
    assert span["gen_ai.operation.name"] == "invoke_agent"
    assert span["gen_ai.agent.name"] == "qa"
    assert span["gen_ai.agent.id"] == "kensho-qa"
    assert span["gen_ai.request.model"] == "deepseek-v4-flash"
    assert span["gen_ai.conversation.id"] == "t_TEST"
    assert span["gen_ai.usage.input_tokens"] == 100
    assert span["gen_ai.usage.output_tokens"] == 50
    assert span["duration_ms"] == 1200
    assert "error.type" not in span, "成功時は error.type を省略する"
    assert span["gen_ai.provider.name"] == emit.DEFAULT_PROVIDER


def test_error_type_present_only_on_failure(tmp_path: Path) -> None:
    ok = emit.build_span(agent="kensho-worker", model="deepseek-v4-flash", conversation_id="t_A")
    ng = emit.build_span(agent="kensho-worker", model="deepseek-v4-flash", conversation_id="t_A",
                         error_type="timeout")
    assert "error.type" not in ok
    assert ng["error.type"] == "timeout"


# ── 2. 追記の非破壊性 ────────────────────────────────────────────────────────

def test_append_is_non_destructive(tmp_path: Path) -> None:
    first = emit.build_span(agent="kensho-critic", model="deepseek-v4-pro", conversation_id="t_1",
                            tokens_in=10, tokens_out=5, duration_ms=300)
    path = emit.append_span(first, DAY, tmp_path)
    before = path.read_bytes()

    second = emit.build_span(agent="kensho-qa", model="deepseek-v4-flash", conversation_id="t_2")
    emit.append_span(second, DAY, tmp_path)

    after = path.read_bytes()
    assert after.startswith(before), "既存行が改変されてはならない"
    assert len(after.splitlines()) == 2
    assert json.loads((tmp_path / f"{DAY}.jsonl").read_text(encoding="utf-8").splitlines()[0]) == first


# ── 3. 壊れた行のスキップ ────────────────────────────────────────────────────

def test_broken_lines_are_skipped_not_counted(tmp_path: Path) -> None:
    valid = emit.build_span(agent="kensho-qa", model="deepseek-v4-flash", conversation_id="t_ok",
                            duration_ms=100)
    broken = [
        "{not json",
        json.dumps([1, 2, 3]),                       # object でない
        json.dumps({"gen_ai.agent.name": "qa"}),      # 必須フィールド欠落
        "",
    ]
    path = tmp_path / f"{DAY}.jsonl"
    path.write_text("\n".join([json.dumps(valid), *broken]) + "\n", encoding="utf-8")

    spans, warnings = report.load_spans(path)
    assert len(spans) == 1
    assert len(warnings) == 3, f"壊れた3行のみ警告（空行は警告しない）: {warnings}"

    agg = report.aggregate(spans)
    assert agg["qa"]["runs"] == 1
    assert agg["qa"]["success_rate"] == 100.0


def test_invalid_numeric_value_warns_and_counts_zero(tmp_path: Path) -> None:
    span = emit.build_span(agent="kensho-worker", model="deepseek-v4-flash", conversation_id="t_x")
    span["gen_ai.usage.input_tokens"] = "abc"
    span["duration_ms"] = -5.0
    path = tmp_path / f"{DAY}.jsonl"
    path.write_text(json.dumps(span) + "\n", encoding="utf-8")

    spans, warnings = report.load_spans(path)
    assert len(spans) == 1, "行自体は有効（値だけ不正）"
    assert len(warnings) == 2
    agg = report.aggregate(spans)
    assert agg["worker"]["tokens_in"] == 0
    assert agg["worker"]["avg_duration_ms"] == 0.0


# ── 4. 集計値の正しさ ────────────────────────────────────────────────────────

def test_aggregate_success_rate_duration_and_tokens() -> None:
    spans = [
        emit.build_span(agent="kensho-qa", model="deepseek-v4-flash", conversation_id="t_1",
                        tokens_in=100, tokens_out=50, duration_ms=1000),
        emit.build_span(agent="kensho-qa", model="deepseek-v4-flash", conversation_id="t_2",
                        tokens_in=200, tokens_out=60, duration_ms=2000),
        emit.build_span(agent="kensho-qa", model="deepseek-v4-flash", conversation_id="t_3",
                        tokens_in=300, tokens_out=70, duration_ms=3000, error_type="timeout"),
        emit.build_span(agent="kensho-critic", model="deepseek-v4-pro", conversation_id="t_4",
                        tokens_in=10, tokens_out=5, duration_ms=500, error_type="timeout"),
    ]
    agg = report.aggregate(spans)
    qa = agg["qa"]
    assert (qa["runs"], qa["ok"], qa["errors"]) == (3, 2, 1)
    assert qa["success_rate"] == 66.7
    assert qa["avg_duration_ms"] == 2000.0
    assert (qa["tokens_in"], qa["tokens_out"], qa["tokens_total"]) == (600, 180, 780)
    assert qa["error_types"] == {"timeout": 1}
    assert agg["critic"]["success_rate"] == 0.0
    assert agg["critic"]["error_types"] == {"timeout": 1}


def test_report_json_output_shape(tmp_path: Path) -> None:
    for i in range(3):
        proc = _run("agent_span_emit.py", [
            "--agent", "kensho-qa", "--model", "deepseek-v4-flash", "--task-id", f"t_{i}",
            "--tokens-in", "10", "--tokens-out", "5", "--duration-ms", "1000", "--date", DAY,
        ], tmp_path)
        assert proc.returncode == 0, proc.stderr

    out = _run("agent_span_report.py", ["--date", DAY, "--json"], tmp_path)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["spans_valid"] == 3
    assert data["agents"]["qa"]["runs"] == 3
    assert data["agents"]["qa"]["success_rate"] == 100.0
    assert data["totals"]["tokens_in"] == 30


def test_text_report_lists_agents(tmp_path: Path) -> None:
    for agent in ("kensho-critic", "kensho-worker", "kensho-qa"):
        for i in range(3):
            proc = _run("agent_span_emit.py", [
                "--agent", agent, "--model", "deepseek-v4-flash", "--task-id", f"t_{agent}_{i}",
                "--duration-ms", "900", "--date", DAY,
            ], tmp_path)
            assert proc.returncode == 0, proc.stderr

    out = _run("agent_span_report.py", ["--date", DAY], tmp_path)
    assert out.returncode == 0, out.stderr
    body = out.stdout
    for role in ("critic", "worker", "qa"):
        assert role in body
    assert body.count("\n") >= 3, "agent別に3行以上を出力する"


# ── 5. cron 安全（exit 0） ───────────────────────────────────────────────────

def test_missing_file_exits_zero_with_warning(tmp_path: Path) -> None:
    out = _run("agent_span_report.py", ["--date", "2099-01-01", "--json"], tmp_path)
    assert out.returncode == 0
    assert "span ファイルがありません" in out.stderr
    data = json.loads(out.stdout)
    assert data["agents"] == {}


def test_empty_file_exits_zero(tmp_path: Path) -> None:
    (tmp_path / f"{DAY}.jsonl").write_text("", encoding="utf-8")
    out = _run("agent_span_report.py", ["--date", DAY], tmp_path)
    assert out.returncode == 0
    assert "spans_valid=0" in out.stdout


def test_fully_broken_file_exits_zero(tmp_path: Path) -> None:
    (tmp_path / f"{DAY}.jsonl").write_text("garbage\n{]\n", encoding="utf-8")
    out = _run("agent_span_report.py", ["--date", DAY], tmp_path)
    assert out.returncode == 0
    assert "壊れたJSON行をスキップ" in out.stderr


# ── 6. 入力バリデーション ───────────────────────────────────────────────────

def test_agent_name_normalized_and_id_preserved(tmp_path: Path) -> None:
    proc = _run("agent_span_emit.py", [
        "--agent", "kensho-revenue-qa", "--model", "deepseek-v4-flash",
        "--conversation-id", "sess_abc", "--date", DAY,
    ], tmp_path)
    assert proc.returncode == 0, proc.stderr
    span = json.loads((tmp_path / f"{DAY}.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert span["gen_ai.agent.name"] == "qa"
    assert span["gen_ai.agent.id"] == "kensho-revenue-qa"
    assert span["gen_ai.conversation.id"] == "sess_abc"


def test_emit_rejects_unknown_agent(tmp_path: Path) -> None:
    proc = _run("agent_span_emit.py", [
        "--agent", "some-random-bot", "--model", "m", "--task-id", "t_x", "--date", DAY,
    ], tmp_path)
    assert proc.returncode == 2
    assert "未知の agent" in proc.stderr
    assert not (tmp_path / f"{DAY}.jsonl").exists(), "不正入力では書き込まない"


def test_emit_rejects_negative_tokens(tmp_path: Path) -> None:
    proc = _run("agent_span_emit.py", [
        "--agent", "kensho-qa", "--model", "m", "--task-id", "t_x", "--tokens-in", "-1", "--date", DAY,
    ], tmp_path)
    assert proc.returncode == 2
    assert not (tmp_path / f"{DAY}.jsonl").exists()


def test_try_emit_span_never_raises(tmp_path: Path, capsys) -> None:
    """テレメトリ失敗で本番フローを止めない（in-process 安全版）."""
    result = emit.try_emit_span(agent="unknown-agent", model="m", conversation_id="t_x",
                                span_dir=tmp_path)
    assert result is None
    assert "warning" in capsys.readouterr().err
