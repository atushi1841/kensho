#!/usr/bin/env python3
import glob
import os
import sys

sys.path.insert(0, os.getcwd())
import scripts.kensho_winrate_analysis as wa

pd = wa.PROJECT_DIR
cp = sorted(glob.glob(os.path.join(pd, "data/collected.json.bak*")) + [os.path.join(pd, "data/collected.json")])
campaigns = wa.load_campaigns(cp)

for target in ["reignstormjp", "apina_katano", "au_official", "netflixjp", "inmist_official", "smbc_midosuke"]:
    print(f"=== {target} ===")
    for k, c in campaigns.items():
        h = (c.get("handle") or "").lower()
        if h == target:
            print(f"  key={k} source={c.get('source')} tweet_id={c.get('tweet_id')} applied={c.get('applied')}")
