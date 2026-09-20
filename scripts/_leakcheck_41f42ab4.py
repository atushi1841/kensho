#!/usr/bin/env python3
import re
BASE="/mnt/d/Project2/kensho"
for fn in [BASE+"/logs/auto_20260920.log", BASE+"/logs/auto_20260919.log"]:
    print("="*60); print(fn.split("/")[-1])
    txt=open(fn,encoding="utf-8",errors="replace").read()
    lines=txt.splitlines()
    toks=[(re.findall(r"(instagra|line\.me|apps\.apple|play\.google|応募フォーム|専用フォーム)", l, re.I)) for l in lines]
    for l in lines:
        if re.search(r"(instagra|line\.me|apps\.apple|play\.google|応募フォーム|専用フォーム)", l, re.I):
            is_skip = ("[SKIP]" in l and "非X" in l)
            tag = "SKIP-line" if is_skip else ("OTHER" if "SKIP" in l else "ACT-LINE?")
            print(f"  [{tag}] {l.strip()[:150]}")
