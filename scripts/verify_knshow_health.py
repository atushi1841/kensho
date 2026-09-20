#!/usr/bin/env python3
import json

path = "data/source_health.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

# 実データ構造: sources は d["sources"] 配下（他主要源 ken-kaku/kenshou.club 等と同型）
sources = d.get("sources", {})
kn = sources.get("knshow")

print("=== d['sources']['knshow'] ===")
print(json.dumps(kn, ensure_ascii=False, indent=2) if kn else "MISSING")

print("\n=== PRIMARY key check ===")
print("knshow key present (nested under sources):", kn is not None)
if kn is not None:
    print("failures>0:", kn["failures"] > 0)
    print("consecutive_failures:", kn["consecutive_failures"])
    print("is_unhealthy condition (consec>=4):", kn["consecutive_failures"] >= 4)
    assert kn["failures"] > 0 and kn["consecutive_failures"] >= 4
    print("\nVERIFY_OK: knshow 実在 + failures={} + consecutive={}>=4 (alert条件を満たす)".format(
        kn["failures"], kn["consecutive_failures"]))
else:
    print("VERIFY_FAIL: knshow not found")
