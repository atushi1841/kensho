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

print("=== FINAL VERIFICATION ===")
for name, aid in actors:
    d = afetch(f"{API}/acts/{aid}?token={TOKEN}").get("data", {})
    versions = d.get("versions") or []
    latest = [v for v in versions if v.get("buildTag") == "latest"]
    sel = latest[-1] if latest else (versions[-1] if versions else None)
    
    print(f"\n--- {name} ({aid}) ---")
    print(f"  isPublic: {d.get('isPublic')}")
    print(f"  pictureUrl: {d.get('pictureUrl')}")
    print(f"  categories: {d.get('categories')}")
    print(f"  seoTitle: {d.get('seoTitle')}")
    print(f"  seoDescription: {d.get('seoDescription')}")
    
    if sel:
        stype = sel.get("sourceType", "?")
        ver = sel.get("versionNumber", "?")
        print(f"  sourceType: {stype}, version: {ver}")
        if stype == "SOURCE_FILES":
            vd = afetch(f"{API}/acts/{aid}/versions/{ver}?token={TOKEN}").get("data", {})
            for f in vd.get("sourceFiles") or []:
                if (f.get("name") or "").lower() == "readme.md":
                    content = f.get("content", "")
                    print(f"  README.md: {len(content)} chars")
                    break
            else:
                print("  README.md: NOT FOUND in sourceFiles")
        elif stype == "GIT_REPO":
            print(f"  gitRepoUrl: {sel.get('gitRepoUrl')}")
    else:
        print(f"  NO VERSIONS")