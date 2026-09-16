#!/usr/bin/env python3
import glob
import os
import sys

sys.path.insert(0, os.getcwd())
import scripts.kensho_winrate_analysis as wa

pd = wa.PROJECT_DIR
cp = sorted(glob.glob(os.path.join(pd, "data/collected.json.bak*")) + [os.path.join(pd, "data/collected.json")])
campaigns = wa.load_campaigns(cp)
from collections import defaultdict

hc = defaultdict(int)
for c in campaigns.values():
    h = c["handle"].lower()
    hc[h] += 1

for h in [
    "reignstormjp",
    "apina_katano",
    "smbc_midosuke",
    "au_official",
    "netflixjp",
    "inmist_official",
    "domin",
    "dominos_jp",
]:
    print(h, "->", hc.get(h, 0))
