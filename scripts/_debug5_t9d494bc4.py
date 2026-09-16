#!/usr/bin/env python3
import glob
import os
import sys

sys.path.insert(0, os.getcwd())

import scripts.kensho_winrate_analysis as wa

pd = wa.PROJECT_DIR
cp = sorted(glob.glob(os.path.join(pd, "data/collected.json.bak*")) + [os.path.join(pd, "data/collected.json")])
campaigns = wa.load_campaigns(cp)
wins = wa.load_wins(os.path.join(pd, "data/dm_wins.json"))

by_tweet = {c["tweet_id"]: c for c in campaigns.values() if c["tweet_id"]}

print("=== conversation_id analysis per win ===")
for w in wins:
    cid = w.get("conversation_id") or ""
    # conversation_id like "54196675-1950738489794048001" -> suffix tweet?
    parts = [p for p in cid.split("-") if p.isdigit()]
    tid_cand = parts[-1] if parts else ""
    snow = wa.tweet_id_to_time_ms(tid_cand)
    import datetime

    snow_dt = datetime.datetime.fromtimestamp(snow / 1000, tz=wa.JST).strftime("%Y-%m-%d") if snow else "?"
    in_camps = tid_cand in by_tweet
    print(f"{w.get('sender'):<18} conv={cid}")
    print(f"   cand_tid={tid_cand} snow_date={snow_dt} in_campaigns={in_camps}")
    # resolve t.co in text
    text = w.get("message_text") or ""
    resolved_targets = []
    for tco in __import__("re").findall(r"https://t\.co/[A-Za-z0-9]+", text):
        r = wa._resolve_tco(tco)
        if r:
            resolved_targets.append(r)
    print(f"   resolved t.co targets: {resolved_targets[:3]}")
