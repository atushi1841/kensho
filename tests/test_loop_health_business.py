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


def _isolated_lh_db(base: Path) -> Path:
    """実盤 kanban.db から独立したダミーDBを base配下に作り --db で固定する (t_1f4779d4)。

    loop_health.sh は --db で解決した _LH_DB に対し kanban_dep_deadlock_guard.py
    （board=ディレクトリ名）・orphan_run_reaper.py・zombieクエリを走らせるため、
    実盤DBを渡すと実盤の ready==0&&todo>0 deadlock(-21) 等の板状態減点が score に
    混入し、business gate のスコア検証が実盤の状態で揺れる。ダミーは tasks>=1 で
    ないと auto-detect が実盤へ再解決されるため running を1行入れる。ディレクトリ名
    lh_db を board 名とするため guard は実盤へ問合せない。
    """
    import sqlite3
    import time

    db_dir = base / "lh_db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db = db_dir / "kanban.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        "id TEXT PRIMARY KEY, status TEXT, last_failure_error TEXT, started_at INTEGER)"
    )
    con.execute("CREATE TABLE IF NOT EXISTS links (parent TEXT, child TEXT, relation TEXT)")
    con.execute(
        "INSERT OR IGNORE INTO tasks (id, status, started_at) VALUES (?, 'running', ?)",
        ("t_lhdummy00000001", int(time.time()) - 3600),
    )
    con.commit()
    con.close()
    return db


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
            "--db",
            str(_isolated_lh_db(tmp_path)),
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


def test_apply_stopped_zero_success_lines_not_completion(tmp_path):
    r"""v170 (critic実測RCA, t_2419836e): 停止時の '完了: 0成功/0エラー' 行は完了扱いしない。

    \d+成功 は '0成功' にもマッチするため、停止中に毎15分書かれる0成功完了行が
    done_count として計上され done_count==0 の停止判定が発動しなかった。
    成功数>=1 の行 ([1-9][0-9]* 成功) のみ完了扱い → 0成功のみのログは stopped。
    """
    out = _run(
        tmp_path,
        [
            "処理待ちのバッチなし",
            "2026-09-17 07:55:14.443 | INFO | _   完了: 0成功/0エラー（0秒）",
            "2026-09-17 08:10:00.000 | INFO | _   完了: 0成功/0エラー（5秒）",
        ],
    )
    assert out["business_done"] == 0  # 0成功行は集計されない
    assert out["business_ok"] is False
    assert out["score"] <= 60


def test_apply_recovered_success_gt0_restores_ok(tmp_path):
    """v170 復旧後: 成功>0 の完了行が1件あれば business_ok=true / score>=80 へ戻る。"""
    out = _run(
        tmp_path,
        [
            "処理待ちのバッチなし",
            "2026-09-17 08:33:03.921 | INFO | _   完了: 15成功/0エラー（1447秒）",
        ],
    )
    assert out["business_done"] >= 1
    assert out["business_ok"] is True
    assert out["score"] >= 80
