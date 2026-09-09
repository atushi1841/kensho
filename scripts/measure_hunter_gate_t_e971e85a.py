#!/usr/bin/env python3
"""t_e971e85a 効果測定 one-shot: 9/10 16:00 hunter実行後のゲート発動を実測する.

critic v74 成功指標①: 「9/10 16:00 実行後、当日新規作成タスク <=3件」
+ 指標② md5一致の再確認 + 指標③ drift-check の出力有無 (OK時サイレント=0バイト,
  検出時 WARN). native crontab one-shot から叩かれ、結果を1行ずつ追記する。
読み取り専用 — 外部状態を変更しない。
"""

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
DB = Path("/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db")
OUT = Path("/home/atushi/.hermes/profiles/kensho-sweeps/state/hunter_gate_measure.log")
REPO = "/mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py"
PROFILE = "/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py"
DRIFT = "/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho_script_drift_check.py"
TARGET_DAY = "2026-09-10"


def md5(path: str) -> str:
    return subprocess.run(["md5sum", path], capture_output=True, text=True).stdout.split()[0]


def main() -> int:
    now = datetime.now(JST)
    day_start = int(datetime.fromisoformat(f"{TARGET_DAY}T00:00:00+09:00").timestamp())
    con = sqlite3.connect(DB)
    cur = con.cursor()
    created_today = cur.execute("SELECT COUNT(*) FROM tasks WHERE created_at >= ?", (day_start,)).fetchone()[0]
    rows = cur.execute(
        "SELECT id, title FROM tasks WHERE created_at >= ? ORDER BY created_at",
        (day_start,),
    ).fetchall()
    con.close()

    m_repo, m_prof = md5(REPO), md5(PROFILE)
    try:
        r = subprocess.run([sys.executable, DRIFT], capture_output=True, text=True, timeout=120)
        drift_out = (r.stdout or "").strip() or f"(silent OK, rc={r.returncode})"
    except Exception as exc:  # noqa: BLE001
        drift_out = f"drift-check ERROR: {exc}"

    verdict = "PASS" if (created_today <= 3 and m_repo == m_prof) else "FAIL"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(
            f"{now.isoformat(timespec='seconds')} t_e971e85a-measure "
            f"created_{TARGET_DAY}={created_today} (limit 3) "
            f"md5_match={m_repo == m_prof} hunter_md5={m_repo} "
            f"drift_check={drift_out.splitlines()[0][:80]} verdict={verdict}\n"
        )
        for tid, title in rows:
            fh.write(f"  + {tid} {title[:70]}\n")
    print(OUT.read_text().splitlines()[-1 - len(rows)])
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
