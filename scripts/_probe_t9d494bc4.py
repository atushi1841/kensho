#!/usr/bin/env python3
import json

def probe(path, label):
    print(f"===== {label} ({path}) =====")
    d = json.load(open(path))
    print("top type:", type(d).__name__)
    if isinstance(d, dict):
        print("keys:", list(d.keys())[:20])
    print()
    return d

wins = probe("data/dm_wins.json", "dm_wins.json")
if isinstance(wins, dict):
    for k, v in wins.items():
        if isinstance(v, list) and v:
            print(f"--- acct={k} rows={len(v)} ---")
            print("row keys:", list(v[0].keys()))
            for i, row in enumerate(v[:3]):
                print(json.dumps(row, ensure_ascii=False)[:800])
            print()
elif isinstance(wins, list):
    if wins:
        print("row keys:", list(wins[0].keys()))
        for i, row in enumerate(wins[:5]):
            print(json.dumps(row, ensure_ascii=False)[:800])

print("\n===== collected.json probe =====")
col = json.load(open("data/collected.json"))
items = col.get("collected") if isinstance(col, dict) else col
print("items:", len(items) if isinstance(items, list) else "N/A")
if isinstance(items, list) and items:
    print("first item keys:", list(items[0].keys()))
    # sample a few with x_url containing /status/
    import re
    cnt = 0
    for it in items:
        x = it.get("x_url") or ""
        if "/status/" in x:
            print(json.dumps(it, ensure_ascii=False)[:400])
            cnt += 1
            if cnt >= 3:
                break
