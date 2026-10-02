#!/usr/bin/env python3
"""Apify Actor カテゴリSpecific化 — Phase 1

t_c33b809a 実装。79 generic-only actor のうち、Apify APIが許可する
特定category（REAL_ESTATE/SPORTS/NEWS/AI/MCP_SERVERS/SOCIAL_MEDIA/BUSINESS/TRAVEL/EDUCATION）
該当ActorにPUTで追加。最大3 category制。変更結果は data/apify_category_update_result.json に記録。

対象actorは data/apify_actors_detail_snapshot.json から抽出（name/title/description マッチ）。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = "/mnt/d/Project2/kensho"
SNAPSHOT = os.path.join(REPO, "data", "apify_actors_detail_snapshot.json")
RESULT = os.path.join(REPO, "data", "apify_category_update_result.json")
GENERIC = {"ECOMMERCE", "AUTOMATION", "DEVELOPER_TOOLS"}

# name/title/description のキーワード → specific category
# 各エントリは (specific_category, [keywords])。先マッチ優先。
MAPPING = [
    ("REAL_ESTATE", ["real-estate", "property-market", "suumo", "rent-market", "realt"]),
    ("SPORTS", ["fishing-tackle", "golf", "motorcycle", "goo-net-car", "upgarage",
                "machinery-scraper", "tackleberry", "goobike"]),
    ("NEWS", ["jma-weather", "egov-laws", "corporate-numbers", "world-bank",
              "eurostat", "jepx"]),
    ("MCP_SERVERS", ["-mcp", "mcp"]),
    ("SOCIAL_MEDIA", ["prize-giveaway", "hotpepper"]),
    ("TRAVEL", ["hotpepper"]),
    ("BUSINESS", ["kakaku-price-search"]),
    ("EDUCATION", ["world-bank", "eurostat"]),
    ("AI", ["anime-figure-price-data", "anime-figure-demand", "kensho-sweep"]),
]

# MCP は MCP_SERVERS が最適だが AI も可。MCP_SERVERS を優先（上記で -mcp が先マッチ）。
# AI は MCP以外のAI系actor専用。


def load_token():
    with open(os.path.join(REPO, ".env")) as f:
        for line in f:
            if line.startswith("APIFY_TOKEN="):
                return line.strip().split("=", 1)[1].split()[0]
    raise SystemExit("APIFY_TOKEN not found")


def classify(actor):
    """actor dict → specific category or None"""
    text = " ".join([
        actor.get("name", ""),
        actor.get("title", "") or "",
        actor.get("description", "") or "",
    ]).lower()
    for cat, kws in MAPPING:
        for kw in kws:
            if kw in text:
                return cat
    return None


def put_categories(tok, actor_id, cats):
    url = f"https://api.apify.com/v2/actors/{actor_id}?token={tok}"
    body = json.dumps({"categories": cats}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r).get("data", {}).get("categories")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main():
    tok = load_token()
    actors = json.load(open(SNAPSHOT))
    generic = [a for a in actors if set(a.get("categories", [])) <= GENERIC]

    targets = []
    for a in generic:
        cat = classify(a)
        if cat and cat not in a.get("categories", []):
            # 最大3 category: 既存2 generic + specific 1（genericが3つの場合は specific で1つ差し替え）
            cur = list(a.get("categories", []))
            if len(cur) >= 3:
                # generic のうち specific と重複しないもの1つを差し替え
                cur = [c for c in cur if c != cat][:2] + [cat]
            else:
                cur = cur + [cat]
            targets.append((a, cat, cur))

    print(f"generic actors: {len(generic)} / targets: {len(targets)}")

    results = []
    ok = fail = 0
    for i, (a, cat, new_cats) in enumerate(targets):
        aid = a["id"]
        status, resp = put_categories(tok, aid, new_cats)
        rec = {
            "actor_id": aid, "name": a["name"], "specific_category": cat,
            "new_categories": new_cats, "status": status, "response": resp,
        }
        results.append(rec)
        if status == 200:
            ok += 1
            print(f"[{i+1}/{len(targets)}] OK {aid} {a['name'][:40]} → {new_cats}")
        else:
            fail += 1
            print(f"[{i+1}/{len(targets)}] FAIL {aid} {status} {str(resp)[:80]}")
        time.sleep(0.3)  # rate limit buffer

    out = {"total_generic": len(generic), "targets": len(targets),
           "ok": ok, "fail": fail, "results": results}
    with open(RESULT, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\nDONE ok={ok} fail={fail} → {RESULT}")


if __name__ == "__main__":
    main()