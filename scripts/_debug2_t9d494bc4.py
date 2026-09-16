#!/usr/bin/env python3
"""Detail which wins went pseudo vs real, and handle+time access."""

import os
import sys
from collections import defaultdict

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

matched, unmatched = wa.match_wins(wins, campaigns)
print(f"{'win sender':<20} {'acct':<10} {'key':<8} {'source':<12} tweet_id")
for m in matched:
    c = m["campaign"]
    w = m["win"]
    print(f"{w.get('sender', ''):<20} {w.get('account_key', ''):<10} {m['key']:<8} {c['source']:<12} {c['tweet_id']}")

print("\n--- For each win, is there a campaign with SAME handle? ---")
handle_counts = defaultdict(int)
for c in campaigns.values():
    if c["handle"]:
        handle_counts[c["handle"]] += 1
for w in wins:
    h = wa.normalize_handle(w.get("sender") or "")
    print(
        f"{w.get('sender'):<20} acct={w.get('account_key'):<10} time={w.get('message_time'):<20} camp_with_handle={handle_counts.get(h, 0)}"
    )

print("\n--- campaigns per handle (top) ---")
for h, n in sorted(handle_counts.items(), key=lambda kv: -kv[1])[:15]:
    print(h, n)
