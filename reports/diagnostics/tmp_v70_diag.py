"""critic v70 diagnostic: inspect collected.json stale-empty and applied structure."""

import importlib.util
import json
import sys
from datetime import datetime

sys.path.insert(0, ".")
spec = importlib.util.spec_from_file_location("bf", "backfill_deadlines.py")
bf = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(bf)
except SystemExit:
    pass

d = json.load(open("data/collected.json", encoding="utf-8"))
c = d["collected"]
print("total", len(c), "ts", str(d.get("timestamp"))[:19])

epoch = 1288834974657


def age_days(it):
    try:
        ms = (int(it.get("tweet_id") or 0) >> 22) + epoch
    except (TypeError, ValueError):
        return None
    return (datetime.now().timestamp() * 1000 - ms) / 86400000.0


def is_applied(it):
    a = it.get("applied") or {}
    return any(v not in (None, "") for v in a.values())


se = []
for it in c:
    if it.get("deadline"):
        continue
    a = age_days(it)
    if a is not None and a > 15:
        applied = it.get("applied") or {}
        se.append((
            it.get("source"),
            is_applied(it),
            sorted([k for k, v in applied.items() if v not in (None, "")]),
            round(a, 1),
        ))
print("stale_empty>15d:", len(se))
for s in se:
    print(" ", s)

print("gate(>15d):", bf.count_stale_empty(c, datetime.now(), 15))
print("total applied-status sample: first item applied=", json.dumps(c[0].get("applied"), ensure_ascii=False))
# count all applied
n_app = sum(1 for it in c if is_applied(it))
print("items with any applied stamp:", n_app)
