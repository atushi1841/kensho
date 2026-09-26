#!/usr/bin/env python3
"""
orphan_run_reaper.py — Detect orphan runs in kanban board.

Read-only detector: NEVER kills processes. Returns JSON with counts for loop_health integration.

Exit codes:
  0 — success (outputs JSON)
  1 — DB error
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

# Paths
DEFAULT_DB = Path.home() / ".hermes" / "kanban.db"


def get_db_path(board: str) -> Path:
    """Resolve board-specific DB path."""
    cand = Path.home() / ".hermes" / "kanban" / "boards" / board / "kanban.db"
    if cand.exists():
        return cand
    return DEFAULT_DB


def run_query(db: Path, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a query and return list of dict rows."""
    try:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        sys.stderr.write(f"ERROR: DB query failed: {e}\n")
        return []


def detect_orphan_runs(db: Path, now: int, stale_threshold: int = 1800) -> Dict[str, Any]:
    """
    Detect three categories of problematic runs:
    1. orphan_runs: task_runs where task_id NOT IN tasks (card deleted)
    2. stale_heartbeat_runs: orphan runs with last_heartbeat_at older than stale_threshold
    3. running_without_pid: orphan runs with status=running and worker_pid IS NULL
    """
    # Orphan runs: run.task_id not in tasks AND status='running' (active orphans only)
    # Stale/ended orphan runs are already cleaned up and don't need penalty.
    orphan_rows = run_query(
        db,
        """
        SELECT r.id, r.task_id, r.status, r.worker_pid, r.last_heartbeat_at, r.started_at
        FROM task_runs r
        LEFT JOIN tasks t ON t.id = r.task_id
        WHERE t.id IS NULL AND r.status = 'running'
        ORDER BY r.started_at ASC
        """
    )

    orphan_count = len(orphan_rows)

    # Stale heartbeat: orphan runs with stale last_heartbeat
    stale_count = 0
    for r in orphan_rows:
        hb = r.get("last_heartbeat_at")
        if hb is not None and (now - hb) > stale_threshold:
            stale_count += 1

    # Running without PID: orphan runs with status=running and no worker_pid
    running_no_pid_count = 0
    for r in orphan_rows:
        if r.get("status") == "running" and r.get("worker_pid") is None:
            running_no_pid_count += 1

    # Build details for JSON output
    details = []
    for r in orphan_rows:
        hb = r.get("last_heartbeat_at")
        details.append({
            "run_id": r["id"],
            "task_id": r["task_id"],
            "status": r["status"],
            "worker_pid": r.get("worker_pid"),
            "last_heartbeat_at": hb,
            "started_at": r.get("started_at"),
            "is_stale": hb is not None and (now - hb) > stale_threshold,
            "running_no_pid": r.get("status") == "running" and r.get("worker_pid") is None,
        })

    return {
        "orphan_runs": orphan_count,
        "stale_heartbeat_runs": stale_count,
        "running_without_pid": running_no_pid_count,
        "details": details,
    }


def main() -> int:
    import argparse
    import time

    parser = argparse.ArgumentParser(description="Detect orphan runs in kanban")
    parser.add_argument("--board", default=os.environ.get("KANBAN_BOARD", "kensho-ai-team"))
    parser.add_argument("--db", help="Explicit DB path (overrides board)")
    parser.add_argument("--json", action="store_true", help="Output JSON (required)")
    parser.add_argument("--stale-threshold", type=int, default=1800, help="Stale heartbeat threshold in seconds (default: 1800)")
    args = parser.parse_args()

    if not args.json:
        sys.stderr.write("ERROR: --json is required\n")
        return 1

    now = int(time.time())

    if args.db:
        db_path = Path(args.db)
    else:
        db_path = get_db_path(args.board)

    if not db_path.exists():
        sys.stderr.write(f"ERROR: DB not found: {db_path}\n")
        return 1

    result = detect_orphan_runs(db_path, now, args.stale_threshold)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())