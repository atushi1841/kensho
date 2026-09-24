#!/usr/bin/env python3
"""Verify the mast_triage.py script produces valid output."""

import json
import subprocess
import sys
import os
import sqlite3

SCRIPT = "/mnt/d/Project2/kensho/scripts/mast_triage.py"
REPORT = "/mnt/d/Project2/kensho/reports/mast_daily.json"
DB = "/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"

def main():
    # 1. Script exists
    if not os.path.exists(SCRIPT):
        print(f"FAIL: script not found at {SCRIPT}")
        return 1
    print(f"PASS: script exists at {SCRIPT}")

    # 2. Script runs without error
    result = subprocess.run(
        [sys.executable, SCRIPT, "--db", DB, "--out", REPORT],
        capture_output=True, text=True
    )
    print("STDOUT:", result.stdout.strip())
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        print(f"FAIL: script exited with {result.returncode}")
        return 1
    print("PASS: script runs successfully (exit 0)")

    # 3. Report is valid JSON with required keys
    with open(REPORT) as f:
        d = json.load(f)

    required_keys = ["generated_at", "dominant_mode", "distribution", "counts", "unclassified", "evidence"]
    for key in required_keys:
        if key not in d:
            print(f"FAIL: missing key '{key}' in report")
            return 1
    print("PASS: report has all required keys")

    # 4. Distribution has all 14 MAST modes
    expected_modes = [
        "FM-1.1", "FM-1.2", "FM-1.3", "FM-1.4", "FM-1.5",
        "FM-2.1", "FM-2.2", "FM-2.3", "FM-2.4", "FM-2.5", "FM-2.6",
        "FM-3.1", "FM-3.2", "FM-3.3",
    ]
    for mode in expected_modes:
        if mode not in d["distribution"]:
            print(f"FAIL: missing mode '{mode}' in distribution")
            return 1
    print("PASS: distribution contains all 14 MAST modes")

    # 5. Total tasks in DB matches classified + unclassified
    conn = sqlite3.connect(DB)
    total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    classified = sum(d["distribution"].values())
    unclassified = len(d["unclassified"])
    if total_tasks != classified + unclassified:
        print(f"FAIL: DB total ({total_tasks}) != classified ({classified}) + unclassified ({unclassified})")
        return 1
    print(f"PASS: DB total ({total_tasks}) = classified ({classified}) + unclassified ({unclassified})")

    # 6. Evidence entries have required fields
    for i, e in enumerate(d["evidence"]):
        for field in ["task_id", "signal", "mode"]:
            if field not in e:
                print(f"FAIL: evidence[{i}] missing field '{field}'")
                return 1
    print(f"PASS: all {len(d['evidence'])} evidence entries have required fields")

    # 7. Dominant mode is valid
    if d["dominant_mode"] not in expected_modes:
        print(f"FAIL: dominant_mode '{d['dominant_mode']}' not in expected modes")
        return 1
    print(f"PASS: dominant_mode '{d['dominant_mode']}' is valid")

    # 8. Counts match DB status counts
    db_counts = dict(conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
    for status, expected_count in [("blocked", d["counts"]["blocked"]),
                                    ("running", d["counts"]["running"]),
                                    ("ready", d["counts"]["ready"])]:
        actual = db_counts.get(status, 0)
        if actual != expected_count:
            print(f"FAIL: {status} count {expected_count} != DB count {actual}")
            return 1
    print(f"PASS: status counts match DB (blocked={d['counts']['blocked']}, running={d['counts']['running']}, ready={d['counts']['ready']})")

    print("\nALL CHECKS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())