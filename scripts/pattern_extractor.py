#!/usr/bin/env python3
"""
pattern_extractor.py — Scan done kanban tasks, extract reusable patterns.

A "pattern" is a class of work that appears repeatedly, identified by:
  1. Script references that recur across tasks (scripts/, tests/, reports/)
  2. Body structure templates (背景/成功指標/検証コマンド sections)
  3. Common verification patterns (commit + pytest + guard)

Usage:
  python3 scripts/pattern_extractor.py --scan-done --min-recurring 2 --output /tmp/patterns.json
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

KANBAN_DB = "/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"


def connect_db() -> sqlite3.Connection:
    con = sqlite3.connect(KANBAN_DB)
    con.row_factory = sqlite3.Row
    return con


def extract_patterns(con: sqlite3.Connection, min_recurring: int = 2):
    """Scan all done tasks and return reusable patterns."""
    cur = con.execute(
        "SELECT id, title, body, result, created_by, created_at "
        "FROM tasks WHERE status = 'done'"
    )
    rows = [dict(r) for r in cur.fetchall()]

    # Count script references across all tasks
    script_counter = Counter()
    test_counter = Counter()
    report_counter = Counter()
    commit_counter = Counter()
    
    # Track task types by body sections
    section_patterns = Counter()
    
    # Track common workflows
    workflow_counter = Counter()
    
    for r in rows:
        body = (r["body"] or "").lower()
        result = (r["result"] or "").lower()
        text = body + " " + result
        
        # Script references
        for m in re.finditer(r"scripts/([\w\-\.]+\.py)", text):
            script_counter[m.group(1)] += 1
        for m in re.finditer(r"tests/([\w\-\.]+\.py)", text):
            test_counter[m.group(1)] += 1
        for m in re.finditer(r"reports/([\w\-\.]+)", text):
            report_counter[m.group(1)] += 1
            
        # Commit patterns
        if "commit" in text:
            commit_counter["has_commit"] += 1
            
        # Section patterns in body
        if "## 背景" in (r["body"] or ""):
            section_patterns["has_background"] += 1
        if "## 成功指標" in (r["body"] or ""):
            section_patterns["has_success_criteria"] += 1
        if "## 検証コマンド" in (r["body"] or ""):
            section_patterns["has_verification_cmds"] += 1
        if "## 受け入れ条件" in (r["body"] or ""):
            section_patterns["has_acceptance_criteria"] += 1
            
        # Workflow patterns
        if "pytest" in text:
            workflow_counter["pytest_verification"] += 1
        if "guard" in text:
            workflow_counter["guard_verification"] += 1
        if "make test" in text or "make lint" in text:
            workflow_counter["make_verification"] += 1

    # Build patterns list
    patterns = []
    
    # Pattern 1: Script-based patterns (scripts that appear 3+ times)
    for script, count in script_counter.most_common():
        if count >= min_recurring:
            patterns.append({
                "type": "script_reference",
                "name": script,
                "count": count,
                "category": "script",
                "description": f"Referenced in {count} done tasks",
                "evidence": f"Appears across multiple task bodies and results",
            })
    
    # Pattern 2: Test-based patterns
    for test, count in test_counter.most_common():
        if count >= 2:
            patterns.append({
                "type": "test_reference",
                "name": test,
                "count": count,
                "category": "test",
                "description": f"Test file referenced in {count} tasks",
                "evidence": f"Part of verification workflow",
            })
    
    # Pattern 3: Structural patterns (body sections)
    for section, count in section_patterns.most_common():
        if count >= 5:  # At least 5 tasks use this structure
            patterns.append({
                "type": "body_structure",
                "name": section,
                "count": count,
                "category": "template",
                "description": f"Body section used in {count} tasks",
                "evidence": f"Common pattern in task specifications",
            })
    
    # Pattern 4: Workflow patterns
    for workflow, count in workflow_counter.most_common():
        if count >= 10:
            patterns.append({
                "type": "workflow",
                "name": workflow,
                "count": count,
                "category": "verification",
                "description": f"Verification step in {count} tasks",
                "evidence": f"Standard practice in done tasks",
            })
    
    return {
        "patterns": patterns,
        "total_done": len(rows),
        "summary": {
            "scripts_referenced": dict(script_counter.most_common(10)),
            "test_files": dict(test_counter.most_common(10)),
            "body_sections": dict(section_patterns.most_common()),
            "workflows": dict(workflow_counter.most_common()),
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Extract reusable patterns from done kanban tasks")
    parser.add_argument("--scan-done", action="store_true", help="Scan all done tasks")
    parser.add_argument("--min-recurring", type=int, default=2, help="Min occurrences for pattern")
    parser.add_argument("--output", type=str, default="/tmp/patterns.json", help="Output JSON path")
    args = parser.parse_args()
    
    if not args.scan_done:
        print("Error: --scan-done required", file=sys.stderr)
        sys.exit(1)
    
    con = connect_db()
    result = extract_patterns(con, args.min_recurring)
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Extracted {len(result['patterns'])} patterns from {result['total_done']} done tasks")
    print(f"Output: {args.output}")
    print(f"\nTop script references: {result['summary']['scripts_referenced']}")


if __name__ == "__main__":
    main()
