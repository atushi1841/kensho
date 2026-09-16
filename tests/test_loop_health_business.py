r"""tests/test_loop_health_business.py — loop_health business KPI gate 完成マーカー修正 (v139, t_e474c675).

実ログの応募完了行は "[OK] 完了: N成功 / Mエラー" と INFO "完了: N成功/Mエラー（Xs秒）" の2形で、
旧 gate の grep "OK 完了" は両方に一致せず常に0 → 稼働日を毎日 business_ok:false の偽陽性WARN にしていた。
v139 は正規表現 r"完了:\s*\d+成功" で実完了行を集計する。本テストがその前提を固定する。
"""

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(
    os.environ.get(
        "LOOP_HEALTH_SCRIPT",
        "/home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh",
    )
)

assert SCRIPT.exists(), f"loop_health.sh not found: {SCRIPT}"


def _run(tmp_path: Path, log_lines: list[str]) -> dict:
    log = tmp_path / "auto_99990101.log"
    log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    state = tmp_path / "state.json"
    env = dict(os.environ)
    env["LOOPHEALTH_LOG_PATH"] = str(log)
    env["LOOPHEALTH_JST_HOUR"] = "14"  # JST 14時 = no_action_window 外
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--tasks",
            "[]",
            "--board",
            "kensho-ai-team",
            "--state",
            str(state),
            "--dry-run",
            "--no-park",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, f"loop_health.sh failed: {proc.stderr}"
    return json.loads(proc.stdout)


def test_working_day_counts_real_completion_lines(tmp_path):
    """稼働日: 実ログ完成行(OK形+INFO形)が数字>0で集計され business_ok=true になる。"""
    out = _run(
        tmp_path,
        [
            "[OK] 完了: 15成功 / 0エラー",
            "2026-09-15 09:00:00.000 | INFO | _   完了: 15成功/0エラー（1秒）",
            "[OK] 完了: 4成功 / 1エラー",
            "[OK] 完了: 0成功 / 2エラー",
            "2026-09-15 12:00:00.000 | INFO | _   完了: 0成功/0エラー（1秒）",
        ],
    )
    assert out["business_done"] >= 1
    assert out["business_ok"] is True
    assert out["score"] >= 90  # 偽陽性WARNで減点されない


def test_stop_day_zero_completion_triggers_warn(tmp_path):
    """停止日: 完了行0 で JST>=9 のとき business_ok=false / score 上限60 / WARN。"""
    out = _run(tmp_path, ["処理待ちのバッチなし"])
    assert out["business_done"] == 0
    assert out["business_ok"] is False
    assert out["score"] <= 60


def test_marker_ok_kanryou_alone_counts_zero(tmp_path):
    """旧 marker 'OK 完了'（実ログに存在しない)は集計されない——修正前のバグを明示。"""
    out = _run(tmp_path, ["OK 完了 done", "biz OK 完了 batch"])
    assert out["business_done"] == 0
    assert out["business_ok"] is False
