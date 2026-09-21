#!/usr/bin/env python3
"""apify_seo_remaining_audit — t_8da22532 用。未完了3項目(icon/categories/version)の実測監査。

token は実行時に .env から読む（shell展開禁止）。読み取り専用。
"""
import json, os, sys, urllib.request
from pathlib import Path

ENV = Path("/mnt/d/Project2/kensho/.env")
API = "https://api.apify.com/v2"

def get_token():
    tok = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
    if not tok and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith(("APIFY_TOKEN_DEFAULT=", "APIFY_TOKEN=")):
                tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return tok

def req(path):
    r = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())

TOKEN = get_token()
assert TOKEN, "no token"

# list my actors
lst = req("/acts?limit=1000&my=1")
actors = lst["data"]["items"][:10]
print(f"total actors(list): {len(actors)}")

rows = []
for a in actors:
    aid = a["id"]
    d = req(f"/acts/{aid}?actor=1")["data"]
    # versions
    ver_info = []
    try:
        vs = req(f"/acts/{aid}/versions")["data"]["items"]
        for v in vs:
            ver_info.append({"versionNumber": v.get("versionNumber"), "buildTag": v.get("buildTag"), "gitRepoUrl": v.get("gitRepoUrl"), "sourceType": v.get("sourceType")})
    except Exception as e:
        ver_info = [{"error": str(e)}]
    # pictureUrl / icon
    picture = d.get("pictureUrl")
    icon = d.get("customIconUrl") or d.get("iconUrl")
    rows.append({
        "id": aid,
        "name": a.get("name"),
        "title": d.get("title") or a.get("title"),
        "isPublic": d.get("isPublic"),
        "pictureUrl": picture,
        "iconLike": icon,
        "categories": d.get("categories"),
        "user": d.get("username"),
        "versionNumbers": [v.get("versionNumber") for v in ver_info if isinstance(v, dict)],
        "versions": ver_info,
        "pricingModel": (d.get("pricingInfos") or [{}])[-1].get("pricingModel") if d.get("pricingInfos") else None,
    })

print(json.dumps(rows, ensure_ascii=False, indent=2))
