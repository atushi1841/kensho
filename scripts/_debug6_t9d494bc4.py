#!/usr/bin/env python3
import json, os, glob

data = json.load(open("data/collected.json"))
items = data.get("collected") if isinstance(data, dict) else data
print("items:", len(items))
have_tweet_id = sum(1 for it in items if it.get("tweet_id"))
print("items with dedicated tweet_id field:", have_tweet_id)
# any x_url WITHOUT /status/ but WITH tweet_id field?
import re
no_status = [it for it in items if it.get("tweet_id") and not re.search(r"/status(?:es)?/", it.get("x_url") or "")]
print("has tweet_id field but no /status in x_url:", len(no_status))
for it in no_status[:5]:
    print("  tweet_id=", it.get("tweet_id"), "x_url=", it.get("x_url"))
# mismatch where x_url status id != tweet_id field
mism = [it for it in items if it.get("tweet_id") and re.search(r"/status(?:es)?/(\d+)", it.get("x_url") or "")]
mm = 0
for it in mism:
    m = re.search(r"/status(?:es)?/(\d+)", it.get("x_url") or "")
    if m and m.group(1) != str(it.get("tweet_id")):
        mm += 1
print("x_url status id != tweet_id field:", mm)
