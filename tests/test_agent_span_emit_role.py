"""tests/test_agent_span_emit_role.py — 役割終了時の span 自動 emit 配線の回帰テスト (t_4ec92f06).

対象:
  scripts/agent_span_emit_role.py  … 役割終了ヘルパーから呼ぶ安全版 emit 入口
  配線先                          … kensho-kanban-sync.sh <role>（critic/worker/qa 共通の末尾ステップ）

観点:
  1. 役割解決（--agent / 環境変数）と、解決不能時に span を書かないこと
  2. **本番を壊さない**（emit 失敗でも exit 0。--strict のときだけ exit 2）
  3. model 解決（--model > env > profile config.yaml > unknown）
  4. conversation.id / duration / tokens の受け渡し
  5. 配線の非回帰（共通ヘルパーに emit 呼び出しが 1 箇所だけ・`|| true` で保護・bash 構文 OK）
  6. 配線の end-to-end（ヘルパーを stub `hermes` 付きで実行 → span が 1 件増える）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import agent_span_emit as emit  # noqa: E402
import agent_span_emit_role as role_emit  # noqa: E402

DAY = "2026-09-24"

#: 配線先（critic の script が $SELF_DIR 経由で呼ぶ実体）
SYNC_HELPER = Path("/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-kanban-sync.sh")
#: 他プロファイル配布コピー（スキル同梱）
SYNC_HELPER_COPIES = (
    Path("/home/atushi/.hermes/profiles/kensho-worker/skills/software-development/"
         "ai-team-improvement/scripts/kensho-kanban-sync.sh"),
    Path("/home/atushi/.hermes/profiles/kensho-sweeps/skills/software-development/"
         "ai-team-improvement/scripts/kensho-kanban-sync.sh"),
)

SPEC_FIELDS = emit.REQUIRED_FIELDS


def _run(args: list[str], out_dir: Path | None = None, extra_env: dict[str, str] | None = None,
         timeout: int = 120) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("HERMES_PROFILE", None)
    env.pop("KENSHO_AGENT_ROLE", None)
    env.pop("KENSHO_MODEL", None)
    env.pop("KENSHO_PROFILE", None)
    if out_dir is not None:
        env["KENSHO_AGENT_SPANS_DIR"] = str(out_dir)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "agent_span_emit_role.py"), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )


def _spans(out_dir: Path) -> list[dict]:
    path = out_dir / f"{DAY}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── 1. 役割解決 ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("agent", "role"), [
    ("critic", "critic"),
    ("worker", "worker"),
    ("qa", "qa"),
    ("kensho-revenue-qa", "qa"),
    ("kensho-worker", "worker"),
])
def test_role_resolution_from_agent_flag(tmp_path: Path, agent: str, role: str) -> None:
    proc = _run(["--agent", agent, "--task-id", "t_TEST", "--date", DAY], tmp_path)
    assert proc.returncode == 0, proc.stderr
    spans = _spans(tmp_path)
    assert len(spans) == 1, "1回の役割終了 = 1 span"
    assert spans[0]["gen_ai.agent.name"] == role
    assert spans[0]["gen_ai.agent.id"] == agent
    assert spans[0]["gen_ai.conversation.id"] == "t_TEST"
    for field in SPEC_FIELDS:
        assert field in spans[0], f"必須フィールド欠落: {field}"
    assert spans[0]["gen_ai.operation.name"] == emit.OPERATION_NAME


def test_role_resolution_from_env(tmp_path: Path) -> None:
    proc = _run(["--date", DAY, "--verbose"], tmp_path,
                extra_env={"KENSHO_AGENT_ROLE": "kensho-qa"})
    assert proc.returncode == 0, proc.stderr
    spans = _spans(tmp_path)
    assert [s["gen_ai.agent.name"] for s in spans] == ["qa"]
    assert "appended 1 span" in proc.stdout


def test_unknown_role_writes_nothing_and_exits_zero(tmp_path: Path) -> None:
    """誤ラベル span で集計を汚さない: 役割不明なら書かずに警告だけ."""
    proc = _run(["--agent", "some-random-bot", "--date", DAY], tmp_path)
    assert proc.returncode == 0, "本番を止めない（既定 exit 0）"
    assert "未知の agent" in proc.stderr
    assert _spans(tmp_path) == [], "役割不明では span を書かない"


def test_missing_role_writes_nothing_and_exits_zero(tmp_path: Path) -> None:
    proc = _run(["--date", DAY], tmp_path)
    assert proc.returncode == 0
    assert "役割が特定できません" in proc.stderr
    assert _spans(tmp_path) == []


def test_strict_mode_surfaces_failure_for_tests(tmp_path: Path) -> None:
    proc = _run(["--agent", "some-random-bot", "--date", DAY, "--strict"], tmp_path)
    assert proc.returncode == 2, "--strict はテスト・人手検証用に失敗を可視化する"


# ── 2. 本番を壊さない（exit 0） ──────────────────────────────────────────────

def test_emit_failure_does_not_change_exit_code(tmp_path: Path) -> None:
    """span 出力先が書けない（パスがファイル）場合でも exit 0 で警告のみ."""
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("x", encoding="utf-8")
    proc = _run(["--agent", "worker", "--date", DAY, "--out-dir", str(blocked)], None)
    assert proc.returncode == 0, proc.stderr
    assert "warning" in proc.stderr


def test_strict_mode_returns_nonzero_on_emit_failure(tmp_path: Path) -> None:
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("x", encoding="utf-8")
    proc = _run(["--agent", "worker", "--date", DAY, "--out-dir", str(blocked), "--strict"], None)
    assert proc.returncode == 2


def test_guard_style_caller_exit_code_is_preserved(tmp_path: Path) -> None:
    """配線（...|| true）と同型の呼び出しで、本体の終了コードが変わらないこと."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("x", encoding="utf-8")
    cmd = (
        f"{sys.executable} {SCRIPTS_DIR / 'agent_span_emit_role.py'} "
        f"--agent worker --out-dir {blocked} --date {DAY} 2>/dev/null || true; echo BODY_EXIT=$?"
    )
    proc = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=env, timeout=120)
    assert "BODY_EXIT=0" in proc.stdout, proc.stdout


def test_try_emit_span_used_in_process_is_safe(tmp_path: Path, capsys) -> None:
    """in-process 経路（import して呼ぶ）も None を返すだけで例外を投げない."""
    result = emit.try_emit_span(agent="unknown-agent", model="m", conversation_id="t_x",
                                span_dir=tmp_path / "not-a-dir")
    assert result is None
    assert "warning" in capsys.readouterr().err


# ── 3. model 解決 ────────────────────────────────────────────────────────────

def test_model_flag_wins(tmp_path: Path) -> None:
    proc = _run(["--agent", "worker", "--model", "acme/model-x", "--date", DAY], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert _spans(tmp_path)[0]["gen_ai.request.model"] == "acme/model-x"


def test_model_from_env(tmp_path: Path) -> None:
    proc = _run(["--agent", "worker", "--date", DAY], tmp_path,
                extra_env={"KENSHO_MODEL": "accounts/fireworks/models/deepseek-v4-flash-0731"})
    assert proc.returncode == 0, proc.stderr
    assert _spans(tmp_path)[0]["gen_ai.request.model"] == "accounts/fireworks/models/deepseek-v4-flash-0731"


def test_model_falls_back_to_profile_config(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    (profiles / "kensho-revenue-worker").mkdir(parents=True)
    (profiles / "kensho-revenue-worker" / "config.yaml").write_text(
        "model:\n  provider: fireworks\n  default: qwen3.8-flash\nmemory:\n  default: x\n",
        encoding="utf-8",
    )
    proc = _run(["--agent", "worker", "--date", DAY], tmp_path,
                extra_env={"HERMES_PROFILES_DIR": str(profiles)})
    assert proc.returncode == 0, proc.stderr
    assert _spans(tmp_path)[0]["gen_ai.request.model"] == "qwen3.8-flash"


def test_model_unknown_when_nothing_resolvable(tmp_path: Path) -> None:
    proc = _run(["--agent", "worker", "--date", DAY], tmp_path,
                extra_env={"HERMES_PROFILES_DIR": str(tmp_path / "empty")})
    assert proc.returncode == 0, proc.stderr
    assert _spans(tmp_path)[0]["gen_ai.request.model"] == role_emit.UNKNOWN_MODEL


def test_profile_model_default_parses_only_model_block(tmp_path: Path) -> None:
    cfg = tmp_path / "profiles" / "kensho-qa"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text(
        "providers:\n  bai:\n    default: should-not-win\nmodel:\n  default: deepseek-v4-flash\n",
        encoding="utf-8",
    )
    assert role_emit.profile_model_default("kensho-qa", tmp_path / "profiles") == "deepseek-v4-flash"
    assert role_emit.profile_model_default("no-such-profile", tmp_path / "profiles") is None


# ── 4. conversation.id / duration / tokens ───────────────────────────────────

def test_conversation_id_and_metrics_passthrough(tmp_path: Path) -> None:
    proc = _run([
        "--agent", "qa", "--conversation-id", "sess_abc", "--tokens-in", "120",
        "--tokens-out", "30", "--duration-ms", "4567", "--error-type", "timeout", "--date", DAY,
    ], tmp_path)
    assert proc.returncode == 0, proc.stderr
    span = _spans(tmp_path)[0]
    assert span["gen_ai.conversation.id"] == "sess_abc"
    assert (span["gen_ai.usage.input_tokens"], span["gen_ai.usage.output_tokens"]) == (120, 30)
    assert span["duration_ms"] == 4567
    assert span["error.type"] == "timeout"


def test_conversation_id_from_task_env_and_duration_from_env(tmp_path: Path) -> None:
    proc = _run(["--agent", "critic", "--date", DAY], tmp_path,
                extra_env={"KENSHO_TASK_ID": "t_FROM_ENV", "KENSHO_DURATION_MS": "900"})
    assert proc.returncode == 0, proc.stderr
    span = _spans(tmp_path)[0]
    assert span["gen_ai.conversation.id"] == "t_FROM_ENV"
    assert span["duration_ms"] == 900


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    proc = _run(["--agent", "critic", "--task-id", "t_X", "--date", DAY, "--dry-run"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["gen_ai.agent.name"] == "critic"
    assert _spans(tmp_path) == [], "--dry-run は書き込まない"


def test_report_counts_emitted_spans(tmp_path: Path) -> None:
    """emit → 集計が繋がっていること（成功指標①の測定経路）."""
    out = tmp_path / "spans"
    for agent in ("critic", "worker", "qa"):
        proc = _run(["--agent", agent, "--task-id", f"t_{agent}", "--date", DAY], out)
        assert proc.returncode == 0, proc.stderr
    report = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "agent_span_report.py"), "--date", DAY, "--json"],
        capture_output=True, text=True, env={**os.environ, "KENSHO_AGENT_SPANS_DIR": str(out)},
        cwd=str(REPO_ROOT), timeout=120,
    )
    assert report.returncode == 0, report.stderr
    data = json.loads(report.stdout)
    assert data["spans_valid"] == 3, "QAの成功指標①（spans_valid>=3）と同一の測定経路"
    assert sorted(data["agents"]) == ["critic", "qa", "worker"]


# ── 5. 配線の非回帰（共通ヘルパー側） ────────────────────────────────────────

@pytest.mark.skipif(not SYNC_HELPER.is_file(), reason="配線先ヘルパーが無い環境")
def test_wiring_call_site_is_single_and_safe() -> None:
    body = SYNC_HELPER.read_text(encoding="utf-8")
    calls = [ln for ln in body.splitlines() if "agent_span_emit_role.py" in ln]
    assert len(calls) == 1, f"emit 呼び出しは 1 箇所だけであること: {calls}"
    call = calls[0]
    assert "|| true" in call, "emit 失敗が本体の終了コードを変えないこと"
    assert '--agent "$ROLE"' in call, "役割は $ROLE をそのまま渡す（捏造しない）"


@pytest.mark.skipif(not SYNC_HELPER.is_file(), reason="配線先ヘルパーが無い環境")
def test_wiring_helper_is_syntactically_valid() -> None:
    for helper in (SYNC_HELPER, *SYNC_HELPER_COPIES):
        if not helper.is_file():
            continue
        proc = subprocess.run(["bash", "-n", str(helper)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"{helper}: {proc.stderr}"


@pytest.mark.skipif(not SYNC_HELPER.is_file(), reason="配線先ヘルパーが無い環境")
@pytest.mark.parametrize("role", ["critic", "worker", "qa"])
def test_wiring_end_to_end_emits_one_span(tmp_path: Path, role: str) -> None:
    """ヘルパーを実走（hermes は stub で無害化）→ span が 1 件増える."""
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "hermes"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    spans = tmp_path / "spans"
    env = {
        **os.environ,
        "PATH": f"{stub_dir}:{os.environ['PATH']}",
        "KENSHO_AGENT_SPANS_DIR": str(spans),
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("KENSHO_AGENT_ROLE", "KENSHO_PROFILE", "HERMES_PROFILE", "KENSHO_MODEL"):
        env.pop(key, None)
    proc = subprocess.run(["bash", str(SYNC_HELPER), role], capture_output=True, text=True,
                          env=env, cwd=str(tmp_path), timeout=180)
    assert proc.returncode == 0, proc.stderr
    written = sorted(spans.glob("*.jsonl"))
    assert len(written) == 1, f"span ファイルが 1 つ生成されること: {proc.stdout} {proc.stderr}"
    spans_found = [json.loads(ln) for ln in written[0].read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(spans_found) == 1
    assert spans_found[0]["gen_ai.agent.name"] == role
    assert all(field in spans_found[0] for field in SPEC_FIELDS)
