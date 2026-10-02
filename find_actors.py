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

# Get all actors
data = afetch(f"{API}/acts?token={TOKEN}&limit=100&desc=1")
actors = data.get("data", {}).get("items", [])

for a in actors:
    name = a.get("name", "")
    if name in ["ai-model-price-api", "japan-jma-weather", "japan-mhlw-medical", "japan-prize-giveaway-scraper", "japan-anime-figure-price-data"]:
        print(f"{name}: {a.get('id')} isPublic={a.get('isPublic')}")