#!/usr/bin/env python3
"""Correlate protocol-violation crashed runs with the two candidate root causes.

Reads the kensho-ai-team kanban DB for crashed runs whose error mentions
'protocol violation', then scans each profile's agent.log* for the signals
that discriminate:

  (a) iteration budget exhaustion  -> 'max_iterations_reached'  / 'kanban stop-loop nudge issued'
  (b) provider outage / LLM death  -> 'API failed after 5 retries' / 'APITimeoutError'
"""
from __future__ import annotations

import collections
import datetime
import glob
import gzip
import os
import re
import sqlite3

DB = "/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"
PROFILES = {
    "kensho-worker": "/home/atushi/.hermes/profiles/kensho-worker/logs",
    "kensho-revenue-worker": "/home/atushi/.hermes/profiles/kensho-revenue-worker/logs",
    "kensho-qa": "/home/atushi/.hermes/profiles/kensho-qa/logs",
    "kensho-revenue-qa": "/home/atushi/.hermes/profiles/kensho-revenue-qa/logs",
    "kensho-critic": "/home/atushi/.hermes/profiles/kensho-critic/logs",
}

SIGNALS = {
    "nudge": "kanban stop-loop nudge issued",
    "maxit": "max_iterations_reached",
    "budget_exhausted": "Iteration budget exhausted",
    "api_dead": "API failed after 5 retries",
    "api_timeout": "APITimeoutError",
    "timed_out_outcome": "budget_used",
}

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


def log_paths() -> list[str]:
    out: list[str] = []
    for prof, d in PROFILES.items():
        for pat in ("agent.log*",):
            for p in sorted(glob.glob(os.path.join(d, pat))):
                out.append(p)
    return out


def iter_lines(path: str):
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", errors="replace") as fh:
            for line in fh:
                yield line
    except OSError:
        return


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select id, task_id, profile, started_at, ended_at, error from task_runs "
        "where coalesce(error,'') like '%protocol violation%' order by started_at"
    ).fetchall()
    print(f"protocol-violation runs total: {len(rows)}")

    # --- per-day histogram of the two discriminators, from the logs (whole-corpus) ---
    per_day = collections.defaultdict(collections.Counter)
    for path in log_paths():
        for line in iter_lines(path):
            m = TS_RE.match(line)
            if not m:
                continue
            day = f"{m.group(1)[5:]}"
            for name, needle in SIGNALS.items():
                if needle in line:
                    per_day[day][name] += 1
    print("\n=== log-signal counts per day (all profiles, agent.log*) ===")
    keys = list(SIGNALS)
    print("  day    " + "".join(f"{k:>17s}" for k in keys))
    for day in sorted(per_day):
        print(f"  {day}  " + "".join(f"{per_day[day][k]:>17d}" for k in keys))

    # --- classify each crashed run by nearest signal in its profile log window ---
    print("\n=== per-run classification (profile log window: [start-5m, end+3m]) ===")
    buckets = collections.Counter()
    day_buckets = collections.defaultdict(collections.Counter)
    detail = []
    for r in rows:
        prof = r["profile"]
        d = PROFILES.get(prof)
        day = datetime.datetime.fromtimestamp(r["started_at"]).strftime("%m-%d")
        if not d:
            buckets["no_log_dir"] += 1
            continue
        lo = r["started_at"] - 300
        hi = (r["ended_at"] or r["started_at"]) + 180
        hits = collections.Counter()
        for p in sorted(glob.glob(os.path.join(d, "agent.log*"))):
            for line in iter_lines(p):
                m = TS_RE.match(line)
                if not m:
                    continue
                ts = datetime.datetime(
                    int(m.group(1)[:4]), int(m.group(1)[5:7]), int(m.group(1)[8:10]),
                    int(m.group(2)), int(m.group(3)), int(m.group(4)),
                ).timestamp()
                if not (lo <= ts <= hi):
                    continue
                for name, needle in SIGNALS.items():
                    if needle in line:
                        hits[name] += 1
        if hits["maxit"] or hits["budget_exhausted"]:
            label = "A_iteration_budget"
        elif hits["api_dead"] or hits["api_timeout"]:
            label = "B_provider_outage"
        elif hits["nudge"]:
            label = "C_nudge_then_exit"
        else:
            label = "D_no_signal"
        buckets[label] += 1
        day_buckets[day][label] += 1
        detail.append((r["id"], r["task_id"], prof, day, label, dict(hits)))

    for k, v in buckets.most_common():
        print(f"  {k:22s} {v:4d}  {v/len(rows)*100:5.1f}%")

    print("\n=== per-day breakdown ===")
    labels = sorted(buckets)
    print("  day    " + "".join(f"{k[:14]:>16s}" for k in labels))
    for day in sorted(day_buckets):
        print(f"  {day}  " + "".join(f"{day_buckets[day][k]:>16d}" for k in labels))

    print("\n=== last 18 runs, detail ===")
    for row in detail[-18:]:
        print("  run%-5s %-18s %-20s %s %-20s %s" % row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
