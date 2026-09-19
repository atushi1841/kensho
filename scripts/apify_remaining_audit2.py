#!/usr/bin/env python3
"""apify_remaining_audit2 — t_8da22532 用並列監査(icon/categories/version/pricing)。読み取り専用。"""
import json, os, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ENV = Path("/mnt/d/Project2/kensho/.env")
API = "https://api.apify.com/v2"

def get_token():
    tok = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
    if not tok and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith(("APIFY_TOKEN_DEFAULT=", "APIFY_TOKEN=")):
                tok = line.split("=", 1)[1].strip().strip('"').strip("'"); break
    return tok

def req(path):
    r = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())

TOKEN = get_token(); assert TOKEN, "no token"
actors = req("/acts?limit=1000&my=1")["data"]["items"]

def inspect(a):
    aid = a["id"]; out = {"id": aid, "name": a.get("name"), "stats": a.get("stats")}
    try:
        d = req(f"/acts/{aid}?actor=1")["data"]
        out["title"] = d.get("title"); out["isPublic"] = d.get("isPublic")
        out["pictureUrl"] = d.get("pictureUrl")
        out["categories"] = d.get("categories")
        pis = d.get("pricingInfos") or []
        out["pricingModel"] = pis[-1].get("pricingModel") if pis else None
        out["modifiedAt"] = d.get("modifiedAt")
        out["statistics"] = d.get("statistics")
    except Exception as e:
        out["err"] = str(e); return out
    try:
        vs = req(f"/acts/{aid}/versions")["data"]["items"]
        out["versions"] = [{"v": v["versionNumber"], "tag": v.get("buildTag"), "st": v.get("sourceType"), "git": bool(v.get("gitRepoUrl"))} for v in vs]
    except Exception as e:
        out["ver_err"] = str(e)
    return out

with ThreadPoolExecutor(max_workers=10) as ex:
    rows = list(ex.map(inspect, actors))
print(json.dumps(rows, ensure_ascii=False))
