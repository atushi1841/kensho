#!/usr/bin/env python3
import re, glob, os
base = "/mnt/d/Project2/kensho"

print("=== A) non-X SKIP in apply logs (7-day) ===")
tot = 0
for fn in sorted(glob.glob(base + "/logs/auto_*.log")):
    d = os.path.basename(fn)
    txt = open(fn, encoding="utf-8", errors="replace").read()
    n = len(re.findall(r"非X導線", txt))
    if n:
        print(f"  {d}: {n}")
        tot += n
print("  window total 非X導線 hits:", tot)

print("\n=== B) non-X that escaped SKIP (applied) ===")
leak = 0
for fn in sorted(glob.glob(base + "/logs/auto_*.log")):
    txt = open(fn, encoding="utf-8", errors="replace").read()
    for l in txt.splitlines():
        if "非X" in l and "SKIP" not in l and ("成功" in l or "適用" in l or "applied" in l or "完了" in l):
            print("  LEAK?", os.path.basename(fn), l[:120]); leak += 1
print("  escapes:", leak)

print("\n=== C) apply success rate today + 7day ===")
def rate(days):
    ok = err = 0; pairs_n = 0
    for fn in glob.glob(base + "/logs/auto_*.log"):
        d = os.path.basename(fn)
        dat = d.replace("auto_", "").replace(".log", "")
        if len(dat) == 8 and int(dat[4:6]) == 9 and (days is None or dat >= days):
            txt = open(fn, encoding="utf-8", errors="replace").read()
            pairs = re.findall(r"\[OK\].*?完了:\s*(\d+)\s*成功\s*/\s*(\d+)\s*エラー", txt)
            for a, b in pairs:
                ok += int(a); err += int(b); pairs_n += 1
    r = round(ok / (ok + err) * 100, 1) if (ok + err) else None
    return ok, err, r, pairs_n
o, e, r, n = rate("20260920")
print(f"  today: {o}成功/{e}エラー = {r}%  ({n} OK-lines)")
o, e, r, n = rate(None)
print(f"  window(all Sep logs): {o}成功/{e}エラー = {r}%  ({n} OK-lines)")

print("\n=== D) collection per run (today) ===")
for fn in sorted(glob.glob(base + "/logs/collect_20260920_*.log")):
    txt = open(fn, encoding="utf-8", errors="replace").read()
    m = re.search(r"(\d+)合計", txt)
    if m:
        print(" ", os.path.basename(fn), "→", m.group(1), "件")

print("\n=== E) artifacts ===")
print("  collected_today.json exists:", os.path.exists(base + "/data/collected_today.json"))
print("  non_x reports:", glob.glob(base + "/reports/non_x_manual_*.md"))
