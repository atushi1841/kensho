#!/usr/bin/env python3
"""regression_gates_ledger — 修正済みバグの回帰ゲート台帳（機械可読JSONをstdoutへ）。

failure→test転換（AgentErrorTaxonomy適用 / t_4e710909）の一部。
reports/failure-taxonomy.md の各行の「再検出コマンド」が返す値の単一の源。

使い方:
    python3 scripts/regression_gates_ledger.py            # JSONをstdoutへ
    python3 scripts/regression_gates_ledger.py --md-table # 分類テーブルをmarkdownで

テスト(tests/test_regression_gates.py)はこのJSONの gates[*].metric を読み、
しきい値と比較する。しきい値違反=該当クラスの再発としてpytest fail。

注意:
- 読み取り専用（kanban.db / cron jobs.json / SKILL.md走査はするが一切書かない）。
- board DBはWALモードなので他の書き手と同時に見えて良い。コピーは使わない
  （コピー基準日を過ぎると検出能力が死ぬ — v94「タイムアウトで全放棄」型の自縄自縛回避）。
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any


def _resolve_home() -> Path:
    """Hermesルートの絶対解決（QA run490: cron起動時はHOME=プロファイル内二重HOMEで
    Path.home() が実体から外れる）。二重HOME側にも.hermesは存在するがkanban board DBを
    持たないため、board DB実在を以て真のHermesルートを判定する。"""
    for root in (Path.home(), Path("/home/atushi")):
        if (root / ".hermes/kanban/boards/kensho-ai-team/kanban.db").exists():
            return root
    return Path("")


HOME = _resolve_home()
KANBAN_DB = HOME / ".hermes/kanban/boards/kensho-ai-team/kanban.db"
PROFILES_GLOB = str(HOME / ".hermes/profiles")

# 運用基準日（critic v151 = guard条件(h)実装commit 505be31 受入完了の夜）。
# この日付より後にdoneしたタスクが result空 だったら再発。
V151_BASELINE_EPOCH = 1789484400.0  # 2026-09-16 00:00:00 JST

# 運用基準日（evolution v103 = チェックポイント+再開プロトコル打刻ルール導入 9/12）。
# この日付より後の timed_out/gave_up run が [checkpoint] コメント0件だったら再発。
V103_BASELINE_EPOCH = 1789224814.0  # 2026-09-12 23:53:34 JST

SKILL_LIMIT_KB = 20
LESSONS_LIMIT_BULLETS = 5


def _db() -> sqlite3.Connection:
    if not KANBAN_DB.exists():
        raise FileNotFoundError(f"kanban board db not found: {KANBAN_DB}")
    con = sqlite3.connect(f"file:{KANBAN_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def metric_result_empty_done() -> dict[str, Any]:
    """doneタスクのresultカラム空（基準日以降、直近48h窓）。

    病理: native kanban_complete(summary=...) のみの完結が構造的にresult空を作る
    (t_274a3024: done16件中15件空)。done_guard.py条件(h)導入後の再発を拾う。
    """
    con = _db()
    window_start = max(V151_BASELINE_EPOCH, time.time() - 48 * 3600)
    total = con.execute(
        "SELECT COUNT(*) c FROM tasks WHERE status='done' AND completed_at>=?",
        (window_start,),
    ).fetchone()["c"]
    empty = con.execute(
        "SELECT COUNT(*) c FROM tasks WHERE status='done' AND completed_at>=? AND (result IS NULL OR TRIM(result)='')",
        (window_start,),
    ).fetchone()["c"]
    offenders = [
        r["id"]
        for r in con.execute(
            "SELECT id FROM tasks WHERE status='done' AND completed_at>=?"
            " AND (result IS NULL OR TRIM(result)='') ORDER BY completed_at DESC",
            (window_start,),
        )
    ]
    return {
        "value": empty,
        "limit": 0,
        "detail": f"done(empty result)={empty}/done(total)={total} since window start, offenders={offenders[:10]}",
    }


def metric_protocol_violation_crash() -> dict[str, Any]:
    """rc=0でcomplete/blockせず終了するプロトコル違反（直近24h）。

    病理: workerが板書せず消える→タスクがreadyへ戻り重複劳动。
    恒久対策はプロンプト側（チェックポイント打刻+完了条件充足即done）なので、
    pytestは再発「検知」のみ担う（ブロッキングし続けることはできない）。
    """
    con = _db()
    cutoff = time.time() - 24 * 3600
    rows = con.execute(
        "SELECT r.task_id, COUNT(*) c FROM task_runs r"
        " WHERE r.outcome='crashed' AND r.started_at>=?"
        " GROUP BY r.task_id",
        (cutoff,),
    ).fetchall()
    offenders = {r["task_id"]: r["c"] for r in rows}
    return {
        "value": sum(offenders.values()),
        "limit": 0,
        "detail": f"crashed rc=0 runs in last 24h: {offenders} (recurring-signal; "
        "triage per-task, do not treat as one-shot)",
    }


def metric_checkpoint_on_exhausted_runs() -> dict[str, Any]:
    """iteration枯渇(timed_out/gave_up) runの[checkpoint]打刻遵守率違反数。

    病理: 90/90枯渇の再ディスパッチはゼロから再走（t_7c64a27c）。
    v103ルール=マイルストーンごとに '[checkpoint] step N done' 打刻。
    基準日以降の枯渇runで打刻0件のタスク数を返す。
    """
    con = _db()
    rows = con.execute(
        "SELECT DISTINCT r.task_id FROM task_runs r WHERE r.outcome IN ('timed_out','gave_up') AND r.started_at>=?",
        (V103_BASELINE_EPOCH,),
    ).fetchall()
    missing = []
    for r in rows:
        tid = r["task_id"]
        cp = con.execute(
            "SELECT COUNT(*) c FROM task_comments WHERE task_id=? AND body LIKE '%[checkpoint]%'",
            (tid,),
        ).fetchone()["c"]
        if cp == 0:
            missing.append(tid)
    return {
        "value": len(missing),
        "limit": 0,
        "detail": f"exhausted runs since v103 without [checkpoint]: {missing}",
    }


def metric_notepad_lessons_bullets() -> dict[str, Any]:
    """cron notepad lessonsの条数上限違反（教訓は鮮度5条ルール）。

    病理: 自由文notepadが無制限に肥大しcompression timeoutを誘発
    (t_252ab0c2: v139で圧縮)。各jobのlessonsについて '- '/'* '始まりの
    箇条書き行数が6以上なら違反として1カウント。
    """
    worst = 0
    worst_job = ""
    n_violations = 0
    scanned = 0
    for p in sorted(Path(PROFILES_GLOB).glob("*/cron/notepad.db")):
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            for job_id, key, val in con.execute("SELECT job_id, key, value FROM cron_notepad WHERE key='lessons'"):
                if not val:
                    continue
                scanned += 1
                bullets = sum(1 for line in val.splitlines() if line.strip().startswith(("- ", "* ")))
                if bullets > LESSONS_LIMIT_BULLETS:
                    n_violations += 1
                if bullets > worst:
                    worst, worst_job = bullets, f"{p.parts[-4]}/{job_id}"
        except sqlite3.Error:
            continue
        finally:
            con.close()
    return {
        "value": n_violations,
        "limit": 0,
        "detail": f"lessons entries scanned={scanned}, max bullets={worst}"
        f" ({worst_job}), limit={LESSONS_LIMIT_BULLETS}, violations={n_violations}",
    }


def _skill_candidates() -> list[Path]:
    paths: list[Path] = []
    paths.extend(Path(PROFILES_GLOB).glob("*/skills/**/SKILL.md"))
    paths.extend((HOME / ".hermes/skills").glob("**/SKILL.md"))
    # repo-internal skills (progressive disclosure target lives here too)
    repo = Path(__file__).resolve().parent.parent
    paths.extend((repo / "skills").glob("**/SKILL.md"))
    return sorted({p for p in paths if p.is_file()})


def metric_skill_md_oversize() -> dict[str, Any]:
    """SKILL.mdサイズ上限（progressive disclosure gate）。

    病理: 44KB→124KBの単一SKILL.mdが毎セッションcontextへ注入され肥大
    (t_a8ede591 / evolution v104)。references/へ分割して20KB以下に保つ。
    """
    limit_bytes = SKILL_LIMIT_KB * 1024
    violations = [p for p in _skill_candidates() if p.stat().st_size > limit_bytes]
    return {
        "value": len(violations),
        "limit": 0,
        "detail": f"SKILL.md > {SKILL_LIMIT_KB}KB: {len(violations)} files,"
        f" e.g. {[str(v.relative_to(HOME)) for v in violations[:3]]}",
    }


def metric_noagent_script_paths() -> dict[str, Any]:
    """no_agent cronジョブのscript解決可能性（argv=scripts_dir/relativeの契約）。

    病理: cron schedulerはargv=[bash|python, <HERMES_HOME>/scripts/<rel>]で実行
    するため、workdir相対や二重ネスト('scripts/x.py')の登録は発火時に
    'Script not found' で全滅する（t_07e4dc05系・教訓notepad 9/6 HIGH BUG）。
    実例(9/15実測): job 352914c18733 script='scripts/dm_scan.py' →
    last_error='Script not found: .../scripts/scripts/dm_scan.py'
    scheduler.pyの解決規則（相対=profileのHERMES_HOME/scripts基準）を再現し、
    enabledなno_agent jobで解決できないものを違反として数える。
    """
    violations: list[str] = []
    checked = 0
    for jp in sorted(Path(PROFILES_GLOB).glob("*/cron/jobs.json")):
        prof = jp.parts[-3]
        profile_scripts = HOME / ".hermes/profiles" / prof / "scripts"
        global_scripts = HOME / ".hermes/scripts"
        try:
            data = json.loads(jp.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for job in data.get("jobs", []):
            if not job.get("no_agent") or not job.get("script"):
                continue
            if not job.get("enabled", True) or job.get("state") in ("paused", "completed"):
                continue
            checked += 1
            raw = job["script"]
            p = Path(raw).expanduser()
            candidates = [p] if p.is_absolute() else [profile_scripts / p, global_scripts / p]
            if not any(c.is_file() for c in candidates):
                violations.append(f"{prof}/{job['id']}:{raw}")
    return {
        "value": len(violations),
        "limit": 0,
        "detail": f"enabled no_agent scripts checked={checked}, unresolvable={violations}",
    }


GATES: dict[str, Any] = {
    "result_column_empty_after_v151": {
        "failure_task": "t_274a3024 (critic v151)",
        "category": "action",
        "func": metric_result_empty_done,
    },
    "protocol_violation_crash_24h": {
        "failure_task": "t_39687587/t_aeb1bb44 (rc=0 silent exits)",
        "category": "action",
        "func": metric_protocol_violation_crash,
    },
    "checkpoint_missing_on_iteration_exhaustion": {
        "failure_task": "t_7c64a27c (evolution v103)",
        "category": "reflection",
        "func": metric_checkpoint_on_exhausted_runs,
    },
    "notepad_lessons_bloat": {
        "failure_task": "t_252ab0c2 (critic v139)",
        "category": "memory",
        "func": metric_notepad_lessons_bullets,
    },
    "skill_md_oversize": {
        "failure_task": "t_a8ede591 (evolution v104)",
        "category": "memory",
        "func": metric_skill_md_oversize,
    },
    "noagent_script_path_contract": {
        "failure_task": "t_07e4dc05 (cron notepad HIGH BUG 9/6)",
        "category": "system",
        "func": metric_noagent_script_paths,
    },
}


def build_ledger() -> dict[str, Any]:
    out: dict[str, Any] = {"generated_at_epoch": time.time(), "gates": {}}
    for name, spec in GATES.items():
        try:
            m = spec["func"]()
        except Exception as e:  # noqa: BLE001 — gate must report, not crash the ledger
            m = {"value": -1, "limit": 0, "detail": f"measurement error: {type(e).__name__}: {e}"}
        out["gates"][name] = {
            "category": spec["category"],
            "failure_task": spec["failure_task"],
            **m,
        }
    return out


def main() -> int:
    ledger = build_ledger()
    if "--md-table" in sys.argv:
        for name, g in ledger["gates"].items():
            status = "FAIL" if g["value"] > g["limit"] else "ok"
            print(
                f"| {name} | {g['category']} | {g['failure_task']} | "
                f"{g['value']}<={g['limit']} {status} | {g['detail']} |"
            )
        return 0
    print(json.dumps(ledger, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
