#!/usr/bin/env python3
import re
BASE = "/mnt/d/Project2/kensho"
logs = sorted(glob_ := __import__("glob").glob(BASE+"/logs/auto_*.log"))
# filter: only recent logs (this month's apply runs after 20260914 to present)
import datetime
def apply_rate(fn):
    txt = open(fn, encoding="utf-8", errors="replace").read()
    # The line `[OK] 完了: X成功 / Yエラー`
    pairs = re.findall(r"完了:\s*(\d+)\s*成功\s*/\s*(\d+)\s*エラー", txt)
    ok = sum(int(a) for a,b in pairs)
    err = sum(int(b) for a,b in pairs)
    return ok, err, pairs

print("Apply success per log (完了: X成功/Yエラー):")
tot_ok=tot_err=0
for fn in logs:
    base = fn.split("/")[-1]
    try:
        ok, err, pairs = apply_rate(fn)
    except Exception as e:
        print(f"  {base}: ERR {e}"); continue
    tot_ok+=ok; tot_err+=err
    if ok or err:
        rate = (ok/(ok+err)*100) if (ok+err) else 0
        print(f"  {base}: {ok}成功 {err}エラー  rate={rate:.1f}%")
print(f"\nTOTAL new-code window (all logs): {tot_ok}成功 / {tot_err}エラー = {tot_ok/(tot_ok+tot_err)*100:.1f}%")

print("\n--- Non-X SKIP lines per log (7-day window) ---")
for fn in logs:
    base = fn.split("/")[-1]
    txt = open(fn, encoding="utf-8", errors="replace").read()
    n = len([l for l in txt.splitlines() if "SKIP" in l and "非X" in l])
    if n: print(f"  {base}: {n}")

print("\n--- Any non-X that actually got processed/applied (leaked)? ---")
for fn in logs:
    base = fn.split("/")[-1]
    txt = open(fn, encoding="utf-8", errors="replace").read()
    # look for SKIP absent + lines that proceed action on a non-X-labeled item — 
    # applier logs label only in skip. Detect if any item with (LINE) etc got action.
    tok = 0
    # crude: action result line referencing instagram/linkline/apps.apple within action context
    for m in re.finditer(r"(instagra|line\.me|apps\.apple|play\.google|応募フォーム|専用フォーム)", txt, re.I):
        tok+=1
    if tok: print(f"  {base}: {tok} non-X-pipeline tokens in apply context")
