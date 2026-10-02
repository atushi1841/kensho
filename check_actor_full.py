#!/usr/bin/env python3
import os
import json
import urllib.request

TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
API = "https://api.apify.com/v2"

def afetch(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())

actors = [
    ("ai-model-price-api", "6EvRs5kF1mbelC03M"),
    ("japan-anime-figure-price-data", "DKzufUSvmuXNKHeYx"),
    ("japan-jma-weather", "1g84gsOT7vE9yxNla"),
    ("japan-mhlw-medical", "62DcoLUAkkOB1hGAH"),
    ("japan-prize-giveaway-scraper", "FPlcw4CWMAKooZNe6"),
]

for name, aid in actors:
    d = afetch(f"{API}/acts/{aid}?token={TOKEN}").get("data", {})
    print(f"\n=== {name} ({aid}) ===")
    print(f"  isPublic: {d.get('isPublic')}")
    print(f"  pictureUrl: {d.get('pictureUrl')}")
    print(f"  categories: {d.get('categories')}")
    print(f"  seoTitle: {d.get('seoTitle')}")
    print(f"  seoDescription: {d.get('seoDescription')}")
    print(f"  description: {d.get('description', '')[:80] if d.get('description') else 'N/A'}...")