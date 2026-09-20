#!/usr/bin/env python3
import json, re, glob, os
BASE = "/mnt/d/Project2/kensho"

print("="*60)
print("A) collected.json state (as currently on disk)")
cj = json.load(open(BASE+"/data/collected.json"))
if isinstance(cj, dict):
    items = cj.get("collected", [])
    print("top-level keys:", list(cj.keys()))
else:
    items = cj
print("total items:", len(items))
if items:
    sample = items[0]
    print("item type:", type(sample))
    print("item keys:", list(sample.keys()) if isinstance(sample,dict) else sample)

from collections import Counter
if items and isinstance(items[0], dict):
    lbl = Counter((x.get("導線","(none)") for x in items))
    print("導線 label distribution:", dict(lbl))
    # how many actually have tweet_text
    has_txt = sum(1 for x in items if x.get("tweet_text"))
    print("with tweet_text:", has_txt, "/", len(items))

print()
print("="*60)
print("B) auto_20260920.apply [SKIP] non-X lines")
at = open(BASE+"/logs/auto_20260920.log").read()
skips = [l for l in at.splitlines() if "SKIP" in l and "非X" in l]
print("非X導線 SKIP count:", len(skips))
for s in skips[:15]:
    print("  ", s[:130])

print()
print("="*60)
print("C) apply success vs error markers in auto_20260920.log")
# look for completion/error markers after apply
comps = re.findall(r"(?:完了|成功|applied付与)[^\n]{0,60}", at)
print("completion-ish count:", len(comps))
for c in comps[:10]:
    print("  ", c[:120])

print()
print("="*60)
print("D) does any submitted item reference non-X paths in apply log?")
for kw in ["LINE","Instagram","Instagram.com","instagram","フォロー&amp;RT","はがき","メール","apps.apple","play.google","LINE@" ]:
    n = at.count(kw)
    if n: print(f"  {kw}: {n}")

print()
print("="*60)
print("E) unique apply actions today (RESULT/POLICY/OK/失敗 lines)")
acts = Counter()
for l in at.splitlines():
    ll = l.strip()
    for marker in ["[RESULT]","[POLICY]","失敗","成功","[OK]","[FAIL]","Error"]:
        if marker in ll:
            m = ll[:110]
            acts[(marker, m.rstrip()) ] += 1
for (mk, m), n in acts.most_common(25):
    print(f"  {n:4d}  {m}")
