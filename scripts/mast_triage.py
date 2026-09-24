#!/usr/bin/env python3
"""
MAST (Multi-Agent System Failure Taxonomy) triage for kensho kanban tasks.

Reads the kanban SQLite database, classifies each task's failure signal into
one of 14 MAST modes, and outputs a JSON report.

Usage:
    python3 mast_triage.py --db /path/to/kanban.db --out /path/to/report.json

The script is read-only: it does not modify the database.
"""

import sqlite3
import json
import argparse
import sys
from datetime import datetime
from collections import defaultdict, Counter

# MAST 14 modes
MAST_MODES = [
    "FM-1.1",  # 指示牌逆
    "FM-1.2",  # 逆刃牌逆
    "FM-1.3",  # 手順牌逆
    "FM-1.4",  # 築褥消失
    "FM-1.5",  # 終了条件の不認識
    "FM-2.1",  # 会話リスト
    "FM-2.2",  # 確認問の嘘言
    "FM-2.3",  # 迷走
    "FM-2.4",  # 情報秘匿
    "FM-2.5",  # 他者入力の無視
    "FM-2.6",  # 推論と行動の敗繆
    "FM-3.1",  # 早すぎる終了
    "FM-3.2",  # 検証の嘘言・不完全
    "FM-3.3",  # 誤って検証
]

def classify_error(last_failure_error: str, block_kind: str) -> str:
    """
    Classify a failure signal into a MAST mode based on error strings and block_kind.
    Returns one of MAST_MODES or None if unclassified.
    """
    if not last_failure_error and not block_kind:
        return None

    error = (last_failure_error or "").lower()
    block = (block_kind or "").lower()

    # Protocol violation patterns -> FM-1.5
    if "protocol violation" in error or "worker exited cleanly (rc=0)" in error:
        return "FM-1.5"

    # Iteration budget exhausted -> FM-1.5
    if "iteration budget exhausted" in error or "(90/90)" in error:
        return "FM-1.5"

    # PID not alive -> FC1 システム設計, map to FM-1.3 (手順牌逆) as a placeholder
    if "pid" in error and "not alive" in error:
        return "FM-1.3"

    # Other patterns can be added here
    # For now, classify anything else as unclassified
    return None

def main():
    parser = argparse.ArgumentParser(description="MAST triage for kanban tasks")
    parser.add_argument("--db", default="/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db",
                        help="Path to kanban SQLite database")
    parser.add_argument("--out", required=True, help="Output JSON report path")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch tasks
    cur.execute("""
        SELECT id, status, last_failure_error, block_kind, consecutive_failures, block_recurrences
        FROM tasks
    """)
    rows = cur.fetchall()

    # Initialize counters
    mode_counter = Counter()
    blocked = running = ready = 0
    unclassified = []
    evidence = []

    for row in rows:
        task_id = row["id"]
        status = row["status"]
        error = row["last_failure_error"]
        block_kind = row["block_kind"]
        # Count statuses
        if status == "blocked":
            blocked += 1
        elif status == "running":
            running += 1
        elif status == "ready":
            ready += 1
        # Classify
        mode = classify_error(error, block_kind)
        if mode is None:
            unclassified.append(task_id)
        else:
            mode_counter[mode] += 1
            evidence.append({
                "task_id": task_id,
                "signal": error or block_kind or "",
                "mode": mode
            })

    # Determine dominant mode
    dominant_mode = None
    if mode_counter:
        dominant_mode = mode_counter.most_common(1)[0][0]

    # Build distribution dict for all 14 modes (including zero counts)
    distribution = {mode: mode_counter.get(mode, 0) for mode in MAST_MODES}

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dominant_mode": dominant_mode,
        "distribution": distribution,
        "counts": {
            "blocked": blocked,
            "running": running,
            "ready": ready
        },
        "unclassified": unclassified,
        "evidence": evidence
    }

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Report written to {args.out}")
    print(f"Dominant mode: {dominant_mode}")
    print(f"Counts: blocked={blocked}, running={running}, ready={ready}")
    print(f"Unclassified: {len(unclassified)}")

if __name__ == "__main__":
    main()