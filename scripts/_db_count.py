"""Print task count for a kanban DB (sqlite3 stdlib).

Used by loop_health.sh `_db_has_tasks()` as a drop-in for `python3 -c`,
which fails under cron's minimal PATH / blocked -c flag.
"""
import sqlite3
import sys

try:
    n = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True).execute(
        "SELECT count(*) FROM tasks"
    ).fetchone()[0]
    print(n)
except Exception:
    print(0)