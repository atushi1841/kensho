#!/usr/bin/env python3
"""Debug matching on real data for t_9d494bc4."""

import os
import sys

sys.path.insert(0, os.getcwd())
import scripts.kensho_winrate_analysis as wa

pd = wa.PROJECT_DIR
campaigns = wa.load_campaigns(
    sorted(
        __import__("glob").glob(os.path.join(pd, "data/collected.json.bak*"))
        + [os.path.join(pd, "data/collected.json")]
    )
)
wins = wa.load_wins(os.path.join(pd, "data/dm_wins.json"))

print("campaigns:", len(campaigns), "wins:", len(wins))
print("campaigns with tweet_id:", sum(1 for c in campaigns.values() if c["tweet_id"]))
print("campaigns with handle:", sum(1 for c in campaigns.values() if c["handle"]))

matched, unmatched = wa.match_wins(wins, campaigns)
print("matched:", len(matched), "unmatched:", len(unmatched))

bykey = {}
pseudo = 0
real_by_handle = 0
for m in matched:
    bykey[m["key"]] = bykey.get(m["key"], 0) + 1
    c = m["campaign"]
    if c["source"] == "unknown" and c["detail_url"] == "":
        pseudo += 1
    elif c["source"] != "unknown":
        real_by_handle += 1
print("key breakdown:", bykey)
print("pseudo campaigns matched:", pseudo, "real-source matched:", real_by_handle)

print("\n--- Wins where extract_tweet_ids finds something ---")
for w in wins:
    ids = wa.extract_tweet_ids(w.get("message_text") or "")
    if ids:
        print(w.get("sender"), w.get("account_key"), "->", ids)

print("\n--- Count of wins mentioning t.co ---")
import re

tcocnt = 0
for w in wins:
    if re.search(r"https://t\.co/", w.get("message_text") or ""):
        tcocnt += 1
print("wins with t.co link:", tcocnt, "of", len(wins))
