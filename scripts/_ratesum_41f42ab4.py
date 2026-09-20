#!/usr/bin/env python3
import re
txt = open("/mnt/d/Project2/kensho/logs/auto_20260920.log", encoding="utf-8").read()

pairs = re.findall(r"\[OK\].*?完了:\s*(\d+)\s*成功\s*/\s*(\d+)\s*エラー", txt)
ok = sum(int(a) for a, b in pairs)
err = sum(int(b) for a, b in pairs)
print("today [OK] pairs:", len(pairs))
print("today OK/ERR:", ok, "/", err,
      "rate=", round(ok / (ok + err) * 100, 1) if ok + err else "NA")

final = re.findall(r"完了:\s*(\d+)\s*成功/(\d+)\s*エラー", txt)
print("final-style total:", sum(int(a) for a, b in final), "/",
      sum(int(b) for a, b in final))

summary = open("/mnt/d/Project2/kensho/logs/summary/2026-09-20.md", encoding="utf-8").read()
print("\n=== summary head ===")
print(summary[:1500])
