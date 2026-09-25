#!/usr/bin/env python3
"""
kanban_dep_deadlock_guard.py — Kanban deadlock detection for kensho-ai-team board.

Detects three conditions that indicate potential deadlock:
  1. ready==0 and todo>0 (no runnable tasks but pending work exists)
  2. todo < 80% of total tasks (less than 80% of all work is ready to run)
  3. reverse edges: a child task is also a parent of a decomposed card (子被分解カードの親)

Outputs:
  - JSON to reports/kanban_deadlock_state.json (structured state)
  - 1-line warning to stdout (for Telegram/notepad)

Exit codes:
  0 — no deadlock detected
  1 — deadlock detected (warning emitted)
  2 — DB error
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

# Paths
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path.home() / ".hermes" / "kanban.db"
STATE_PATH = ROOT / "reports" / "kanban_deadlock_state.json"
BOARD_NAME = os.environ.get("KANBAN_BOARD", "kensho-ai-team")

# ──────────────────────────────────────────────────────────────────────────────
# DB utilities
# ──────────────────────────────────────────────────────────────────────────────
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

# ──────────────────────────────────────────────────────────────────────────────
# Kanban state fetching
# ──────────────────────────────────────────────────────────────────────────────
def fetch_tasks(db: Path) -> Dict[str, Any]:
    """Fetch all tasks with key fields for deadlock detection."""
    tasks = run_query(
        db,
        """
        SELECT id, status, title, created_at
        FROM tasks
        WHERE status NOT IN ('archived', 'abandoned')
        ORDER BY created_at DESC
        """
    )
    return {t["id"]: t for t in tasks}

def fetch_links(db: Path) -> List[Dict[str, Any]]:
    """Fetch all parent-child links."""
    return run_query(
        db,
        """
        SELECT parent_id, child_id
        FROM task_links
        """
    )

# ──────────────────────────────────────────────────────────────────────────────
# Deadlock detection logic
# ──────────────────────────────────────────────────────────────────────────────
def detect_deadlock(tasks: Dict[str, Any], links: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze tasks/links and return deadlock state."""
    total = len(tasks)
    if total == 0:
        return {
            "ready": 0,
            "todo": 0,
            "running": 0,
            "blocked": 0,
            "scheduled": 0,
            "total": 0,
            "cond1_ready_zero": False,
            "cond2_todo_lt_80": False,
            "reverse_edges": [],
            "deadlock": False,
            "reason": "empty board"
        }

    ready = sum(1 for t in tasks.values() if t["status"] == "ready")
    todo = sum(1 for t in tasks.values() if t["status"] == "todo")
    running = sum(1 for t in tasks.values() if t["status"] == "running")
    blocked = sum(1 for t in tasks.values() if t["status"] == "blocked")
    scheduled = sum(1 for t in tasks.values() if t["status"] == "scheduled")

    # Condition 1: ready==0 and todo>0
    cond1 = ready == 0 and todo > 0

    # Condition 2: todo < 80% of total
    cond2 = todo > 0 and (todo / total) < 0.8

    # Condition 3: reverse edges (child is also a parent of a decomposed card)
    # Build adjacency from task_links
    child_to_parents: Dict[str, List[str]] = {}
    parent_to_children: Dict[str, List[str]] = {}

    for link in links:
        child_id = link["child_id"]
        parent_id = link["parent_id"]

        child_to_parents.setdefault(child_id, []).append(parent_id)
        parent_to_children.setdefault(parent_id, []).append(child_id)

    reverse_edges = []
    for child_id, parents in child_to_parents.items():
        for parent_id in parents:
            # Check if this child is also a parent of a decomposed card
            # A decomposed card's children are those that have it as parent in task_links
            if child_id in parent_to_children:
                # This child is also a parent of other tasks
                children = parent_to_children[child_id]
                for grandchild in children:
                    # Check if grandchild has parent_id in its parents list
                    # (i.e., grandchild's parent list includes parent_id)
                    grandchild_parents = child_to_parents.get(grandchild, [])
                    if parent_id in grandchild_parents:
                        reverse_edges.append({
                            "child": child_id,
                            "parent": parent_id,
                            "grandchild": grandchild,
                            "child_task_title": tasks.get(child_id, {}).get("title", "")[:50],
                            "parent_task_title": tasks.get(parent_id, {}).get("title", "")[:50],
                        })

    # Overall deadlock flag
    deadlock = cond1 or cond2 or (len(reverse_edges) > 0)

    reason_parts = []
    if cond1:
        reason_parts.append(f"ready==0 && todo>0 ({ready} ready, {todo} todo)")
    if cond2:
        ratio = (todo / total) * 100
        reason_parts.append(f"todo={todo} ({ratio:.1f}% of {total})")
    if len(reverse_edges) > 0:
        reason_parts.append(f"reverse edges {len(reverse_edges)}")

    reason = ", ".join(reason_parts) if reason_parts else "none"

    return {
        "ready": ready,
        "todo": todo,
        "running": running,
        "blocked": blocked,
        "scheduled": scheduled,
        "total": total,
        "cond1_ready_zero": cond1,
        "cond2_todo_lt_80": cond2,
        "reverse_edges": reverse_edges,
        "deadlock": deadlock,
        "reason": reason,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────────────────────────────────────
def write_state(state: Dict[str, Any]) -> None:
    """Write deadlock state JSON to reports directory."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def emit_warning(state: Dict[str, Any]) -> str:
    """Generate 1-line warning for Telegram/notepad."""
    if not state["deadlock"]:
        return ""

    parts = []
    if state["cond1_ready_zero"]:
        parts.append(f"ready=0, todo={state['todo']} (blocked)")
    if state["cond2_todo_lt_80"]:
        ratio = (state["todo"] / state["total"]) * 100 if state["total"] > 0 else 0
        parts.append(f"todo={state['todo']} ({ratio:.1f}%)")
    if state["reverse_edges"]:
        parts.append(f"reverse edges {len(state['reverse_edges'])}")

    warning = f"DEADLOCK DETECTED: {', '.join(parts)}"
    return warning

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Kanban deadlock detection")
    parser.add_argument("--board", default=BOARD_NAME, help="Kanban board name")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    db_path = get_db_path(args.board)
    if not db_path.exists():
        sys.stderr.write(f"ERROR: DB not found: {db_path}\n")
        return 2

    tasks = fetch_tasks(db_path)
    links = fetch_links(db_path)
    state = detect_deadlock(tasks, links)

    write_state(state)

    if args.json:
        print(json.dumps(state, ensure_ascii=False))
        return 0 if not state["deadlock"] else 1

    warning = emit_warning(state)
    if warning:
        print(warning)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())