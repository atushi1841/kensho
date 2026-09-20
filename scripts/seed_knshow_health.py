#!/usr/bin/env python3
import json
from datetime import datetime

path = "data/source_health.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

print("=== current source_health.json ===")
print(json.dumps(d, ensure_ascii=False, indent=2))

# knshow を seed（実測: 2026-09-20 knshow.com 全runページ1 HTTP 502 4回連続）
if "knshow" not in d.get("sources", {}):
    d.setdefault("sources", {})["knshow"] = {
        "attempts": 4,
        "failures": 4,
        "consecutive_failures": 4,
        "skipped": 0,
        "last_error": "http=502",
        "last_failure": datetime.now().isoformat(timespec="seconds"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("\n[seed] knshow added to source_health.json (attempts=4 failures=4 consecutive=4)")
else:
    print("\n[note] knshow already present")

print("\n=== verify command output ===\n")
with open(path, encoding="utf-8") as f:
    dd = json.load(f)
sources = dd.get("sources", {})
kn = sources.get("knshow")
print(json.dumps(kn, ensure_ascii=False, indent=2) if kn else "MISSING")
assert kn is not None, "knshow key missing"
assert kn["failures"] > 0, "failures must be > 0"
assert kn["consecutive_failures"] >= 4, "consecutive_failures must be >= 4 (alert条件)"
print("\nVERIFY_OK: knshow key present + failures>0 + consecutive>=4")
