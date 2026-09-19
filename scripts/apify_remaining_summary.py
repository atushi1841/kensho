#!/usr/bin/env python3
"""Summarize audit2.json for the 3 unfinished items."""
import json
rows = json.load(open("/tmp/audit2.json"))
print(f"total={len(rows)}")
pub = [r for r in rows if r.get("isPublic")]
print(f"public={len(pub)}")
print("\n-- categories state (public only) --")
from collections import Counter
catc = Counter(tuple(sorted(r.get("categories") or [])) for r in pub)
for k,v in catc.items(): print(f"  {v}x {k}")
print("\n-- pictureUrl empty (public) --")
nopic = [r for r in pub if not r.get("pictureUrl")]
print(f"  {len(nopic)} without pictureUrl")
for r in nopic: print(f"    {r['name']}")
print("\n-- non-PPE pricingModel (public) --")
for r in pub:
    pm = r.get("pricingModel")
    if pm and pm != "PAY_PER_EVENT" and pm != "PPE":
        print(f"  {r['name']}: {pm}")
print("\n-- version counts --")
for r in pub:
    vs = r.get("versions") or []
    tags = [v.get("tag") for v in vs]
    print(f"  {r['name']}: n{len(vs)} tags={tags} git={[v.get('git') for v in vs]}")
print("\n-- errors --")
for r in rows:
    if r.get("err"): print(f"  {r['name']} ERR {r['err']}")
    if r.get("ver_err"): print(f"  {r['name']} VERERR {r['ver_err']}")
print("\n-- sample full record (first public) --")
if pub: print(json.dumps(pub[0], ensure_ascii=False, indent=2))
