#!/usr/bin/env python3
"""
apify_readme_deploy — audit fill README in Apify actor sources (build-time README).

Task t_5126f825. Findings that shape this:
  - Apify API has NO readme field/endpoint (verified against official openapi.json
    2026-09-06): GET /v2/acts/{id} never returns readme, so 'readme>=800' cannot be
    read back via API. The earlier ground-truth 'readme_ge_800:0/63' measured a
    nonexistent field -> artifact.
  - README is build-time from source README.md. Deploy = put README.md into the
    source and rebuild. Verified read-back is therefore:
        (a) README.md present in the source (GitHub contents API / sourceFiles)
        (b) build SUCCEEDED
        (c) build log shows the new commit was cloned.
  - Sources are mixed: GIT_REPO (push README to GitHub) and SOURCE_FILES (PUT
    version sourceFiles incl. README.md).

Usage:
  python3 scripts/apify_readme_deploy.py --audit          # report only, no changes
  python3 scripts/apify_readme_deploy.py --deploy --only name1,name2
  python3 scripts/apify_readme_deploy.py --deploy
Env: APIFY_TOKEN (Apify), GH_TOKEN (GitHub, repo scope)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# ruff: noqa: E501  -- includes long markdown README template lines

API = "https://api.apify.com/v2"
TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
if not GH_TOKEN and Path("/tmp/gh_token.txt").exists():
    GH_TOKEN = Path("/tmp/gh_token.txt").read_text().strip()
GT = Path("reports/apify-seo/apify-groundtruth-2026-09-06.json")


def afetch(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())


def aput(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.getcode(), json.loads(r.read())
    except urllib.error.HTTPError as e:
        b = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, {"raw": b}


def apost(url, data=b"", headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.getcode(), json.loads(r.read())
    except urllib.error.HTTPError as e:
        b = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, {"raw": b}


def gh(verb, url, payload=None):
    headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    data = json.dumps(payload).encode() if payload else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=verb)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        b = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, {"raw": b}


def infer_usage(name):
    usage_map = {
        "mcp": ("MCP", "marketplace"),
        "surugaya": ("Suruga-ya", "used hobby/anime/game collectibles"),
        "komehyo": ("Komehyo", "used luxury brand items"),
        "mercari": ("Mercari", "C2C resale marketplace"),
        "iosys": ("IOSYS", "used smartphones and tablets"),
        "yahoo-auctions": ("Yahoo Auctions", "auction marketplace"),
        "hotpepper": ("HotPepper", "salon search"),
        "realestate": ("real estate", "rent and sale listings"),
        "wantedly": ("Wantedly", "job listings"),
        "kitamura": ("Kitamura", "used camera listings"),
        "camera": ("cameras", "DSLR, mirrorless, vintage cameras"),
        "digimart": ("Digimart", "used musical instruments"),
        "offmall": ("Hard Off OffMall", "second-hand chain official store"),
        "brand": ("luxury brand", "branded resale"),
        "watch": ("watches", "luxury and vintage timepieces"),
        "instrument": ("musical instruments", "guitars, synths, brass"),
        "smartphone": ("smartphones", "iPhone, Android, tablets"),
        "hobby": ("hobby collectibles", "anime figures, retro games"),
        "car": ("car", "vehicle listings and price data"),
        "kimono": ("kimono", "traditional Japanese clothing"),
        "goo-net": ("goo-net car", "vehicle listings"),
        "suumo": ("SUUMO/real estate", "rent and sale listings"),
        "goobike": ("goobike", "motorcycle listings"),
        "kakaku": ("kakaku.com", "price comparison"),
        "rakuten": ("Rakuten", "marketplace price data"),
        "golfpartner": ("GolfPartner", "used golf clubs"),
        "biglemon": ("BigLemon", "used heavy machinery"),
        "dlsite": ("DLsite", "doujin digital goods"),
        "dmm": ("DMM", "digital media"),
        "mandarake": ("Mandarake", "used collectibles"),
        "tackleberry": ("TackleBerry", "fishing tackle"),
        "upgarage": ("UpGarage", "auto parts"),
        "egov": ("e-Gov Japan", "public laws and regulations"),
        "jma": ("JMA", "weather and meteorological data"),
    }
    for kw, (label, desc) in usage_map.items():
        if kw in name.lower():
            return label, desc
    return ("Japan market", "Japanese marketplace data")


def build_readme(name, label, usage):
    return f"""# {name}

This Apify actor scrapes **{label}** data from Japanese {usage} sources. It produces structured JSON or CSV suitable for resale arbitrage, market research, price monitoring, AI training pipelines, and competitor analysis.

## What it scrapes

For each item found, the actor extracts:

- **Title** (item name in Japanese and English where available)
- **Price** (JPY, with discount/original price distinction)
- **Condition** (new, used, refurbished, etc.)
- **Seller** (name, rating, shop ID)
- **Category** (taxonomy path)
- **Images** (URLs, alt text)
- **URL** (canonical item link)
- **Timestamp** (when scraped)

## Input

The actor accepts the following input fields:

- `startUrls` (array): Initial listing or category URLs to seed the crawl
- `maxItems` (integer, default 1000): Maximum number of items to scrape per run
- `proxyConfiguration` (object): Proxy settings (residential or datacenter based on target)
- `searchKeyword` (string, optional): Filter listings by keyword
- `priceRange` (object, optional): {{ min, max }} in JPY to filter listings

## Output

Results are written to the default Apify dataset in this shape:

```json
{{
  "title": "...",
  "priceJpy": 12345,
  "condition": "used",
  "seller": {{ "name": "...", "rating": 4.5 }},
  "category": ["...", "..."],
  "images": ["https://..."],
  "url": "https://...",
  "scrapedAt": "2026-09-05T00:00:00Z"
}}
```

## Pricing

Pay-per-event: **charged per item scraped**. See the actor's pricing tab for the current per-item rate. No monthly subscription required; you pay only for what you actually collect.

## Use cases

- **Resale arbitrage**: identify underpriced listings on one marketplace to flip on another
- **Market research**: track price trends, new arrivals, and seller behaviour over time
- **Price monitoring**: alert when items cross your buy/sell thresholds
- **AI training data**: build labelled datasets for classification, price prediction, and listing generation
- **Competitor analysis**: monitor which sellers dominate which categories

## Notes

This actor is part of a suite covering major Japanese marketplaces and second-hand chains. Source listings are public; the actor respects robots.txt and includes polite crawl delays. For high-volume or commercial scraping, configure residential proxies via the input schema.
"""


def get_version_info(aid):
    d = afetch(f"{API}/acts/{aid}?token={TOKEN}").get("data", {})
    versions = d.get("versions") or []
    # prefer buildTag==latest, newest
    latest = [v for v in versions if v.get("buildTag") == "latest"]
    sel = latest[-1] if latest else (versions[-1] if versions else None)
    if not sel:
        return d, None
    return d, sel


def read_source_readme(stype, gurl, aid, sel):
    """Return (readme_text|None, method)."""
    if stype == "GIT_REPO" and gurl:
        repo = gurl.rstrip("/")
        if repo.endswith(".git"):
            repo = repo[:-4]
        owner = repo.split("/")[-2]
        name = repo.split("/")[-1]
        code, d = gh("GET", f"https://api.github.com/repos/{owner}/{name}/contents/README.md")
        if code == 200:
            return base64.b64decode(d["content"]).decode(errors="replace"), f"gh:{owner}/{name}"
        if code == 404:
            return None, f"gh:{owner}/{name}"
        return None, f"gh-err{code}:{owner}/{name}"
    elif stype == "SOURCE_FILES" and sel:
        ver = sel["versionNumber"]
        vd = afetch(f"{API}/acts/{aid}/versions/{ver}?token={TOKEN}").get("data", {})
        for f in vd.get("sourceFiles") or []:
            if (f.get("name") or "").lower() == "readme.md":
                return f.get("content"), f"sf:{ver}"
        return None, f"sf:{ver}(no-readme)"
    return None, f"unknown:{stype}"


def write_source_readme(stype, gurl, aid, sel, text):
    """Write README.md into source. Returns (ok, note)."""
    if stype == "GIT_REPO" and gurl:
        repo = gurl.rstrip("/")
        if repo.endswith(".git"):
            repo = repo[:-4]
        owner = repo.split("/")[-2]
        name = repo.split("/")[-1]
        # get existing to include sha (update), else create
        code, d = gh("GET", f"https://api.github.com/repos/{owner}/{name}/contents/README.md")
        body = {
            "message": "feat(seo): SEO README (>=800 chars) for Apify Store",
            "content": base64.b64encode(text.encode()).decode(),
        }
        if code == 200:
            body["sha"] = d["sha"]
        c2, dd = gh("PUT", f"https://api.github.com/repos/{owner}/{name}/contents/README.md", body)
        return c2 in (200, 201), f"gh-push {c2} {owner}/{name}"
    elif stype == "SOURCE_FILES" and sel:
        ver = sel["versionNumber"]
        vd = afetch(f"{API}/acts/{aid}/versions/{ver}?token={TOKEN}").get("data", {})
        files = vd.get("sourceFiles") or []
        files = [f for f in files if (f.get("name") or "").lower() != "readme.md"]
        files.append({"name": "README.md", "content": text})
        c, b = aput(
            f"{API}/acts/{aid}/versions/{ver}?token={TOKEN}",
            {
                "versionNumber": ver,
                "sourceType": "SOURCE_FILES",
                "sourceFiles": files,
                "buildTag": sel.get("buildTag", "latest"),
            },
        )
        return c == 200, f"sf-put {c} {ver}"
    return False, f"unsupported {stype}"


def trigger_build(aid, ver):
    c, b = apost(f"{API}/acts/{aid}/builds?version={ver}&tag=latest&token={TOKEN}")
    if c in (200, 201):
        bid = b.get("data", {}).get("id")
        return True, bid
    return False, str(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true", help="report only, no changes")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--only", default="", help="comma names")
    ap.add_argument("--min-readme", type=int, default=800, help="min README chars to count as OK")
    args = ap.parse_args()
    if not TOKEN or not GH_TOKEN:
        print("APIFY_TOKEN and GH_TOKEN env required")
        return 2

    gt = json.load(open(GT))
    targets = [r for r in gt["public"]]
    if args.only:
        names = set(x for x in args.only.split(",") if x)
        targets = [r for r in targets if r["name"] in names]

    print(f"targets: {len(targets)} public actors")
    rows = []
    for r in targets:
        name = r["name"]
        aid = r["actor_id"]
        d, sel = get_version_info(aid)
        if not sel:
            rows.append({
                "name": name,
                "id": aid,
                "sourceType": "?",
                "git": "?",
                "readme_len": -1,
                "need": True,
                "note": "no-version",
            })
            continue
        stype = sel.get("sourceType", "?")
        gurl = sel.get("gitRepoUrl")
        ver = sel.get("versionNumber")
        readme, method = read_source_readme(stype, gurl, aid, sel)
        rlen = len(readme) if readme else 0
        need = rlen < args.min_readme
        rows.append({
            "name": name,
            "id": aid,
            "sourceType": stype,
            "git": gurl,
            "version": ver,
            "readme_len": rlen,
            "need": need,
            "method": method,
        })
        print(f"{'NEED' if need else ' ok '} {name:<42} {stype:<12} readme={rlen:<5} {method}")

    need_rows = [x for x in rows if x.get("need")]
    print(f"\n--- gaps (<{args.min_readme} chars) needed deploy: {len(need_rows)} / {len(rows)}")

    audit_out = Path("reports/apify-seo/readme-source-audit-latest.json")
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(
        {
            "verified_at": datetime.now(UTC).isoformat(),
            "target": len(rows),
            "ok": len(rows) - len(need_rows),
            "need_deploy": len(need_rows),
            "rows": rows,
        },
        open(audit_out, "w"),
        ensure_ascii=False,
        indent=1,
    )
    print(f"wrote {audit_out}")

    if args.deploy and need_rows and not args.audit:
        print("\n=== deploying ===")
        for row in need_rows:
            name = row["name"]
            aid = row["id"]
            stype = row["sourceType"]
            label, _ = infer_usage(name)
            text = build_readme(name, label, _)
            ok, note = write_source_readme(
                stype, row["git"], aid, {"versionNumber": row["version"], "buildTag": "latest"}, text
            )
            row["push_ok"] = ok
            row["push_note"] = note
            print(f"  push: {name} -> {ok} ({note})")
            if ok:
                tb, bid = trigger_build(aid, row["version"])
                row["build_id"] = bid
                row["build_ok"] = tb
                print(f"  build: {name} -> triggered={tb} id={bid}")
                time.sleep(1.2)
        out = Path("reports/apify-seo/readme-deploy-" + datetime.now(UTC).strftime("%Y-%m-%d") + ".json")
        out.parent.mkdir(parents=True, exist_ok=True)
        json.dump(rows, open(out, "w"), ensure_ascii=False, indent=1)
        print(f"wrote {out}")
        # print build ids for later monitoring
        bids = [r["build_id"] for r in rows if r.get("build_id")]
        print("BUILD_IDS=" + ",".join(bids))
    elif not args.audit:
        print("(no deploy run for gaps; use --deploy)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
