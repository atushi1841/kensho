#!/usr/bin/env python3
"""Diagnose protocol-violation crashed runs on the kensho-ai-team board."""
import sqlite3
import datetime
import collections
import sys

DB = "/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

rows = c.execute(
    "select id, task_id, profile, started_at, ended_at, outcome, error "
    "from task_runs where coalesce(error,'') like '%protocol violation%' order by started_at"
).fetchall()
print("total protocol-violation runs:", len(rows))

per_day = collections.Counter()
for r in rows:
    d = datetime.datetime.fromtimestamp(r["started_at"]).strftime("%m-%d")
    per_day[d] += 1
for d in sorted(per_day):
    print("  ", d, per_day[d])

print()
print("last 25, newest first:")
for r in list(reversed(rows))[:25]:
    ts = datetime.datetime.fromtimestamp(r["started_at"]).strftime("%m-%d %H:%M")
    dur = (r["ended_at"] - r["started_at"]) if r["ended_at"] else -1
    print(f"  run{r['id']} {r['task_id']} {r['profile']:22s} {ts} dur={dur:6d}s "
          f"{(r['error'] or '')[:120]}")

print()
print("=== error message shapes (normalized) ===")
shapes = collections.Counter()
for r in rows:
    e = r["error"] or ""
    shapes[e.strip()[:200]] += 1
for s, n in shapes.most_common(10):
    print(f"  {n:4d}  {s}")
