#!/usr/bin/env python3
"""apify_verify_groundtruth — 64アクターの実地状態を individual GET (QA指定)で検証。

QA v29/v30 の指摘: リストGET (/v2/acts?my=true) は description/seo* を返さず、
「未適用」と誤判定された。本スクリプトは個別GET (/v2/acts/{id}) のみを使い、
実地の description/readme/seoTitle/seoDescription/categories 長を確認する。

用法: APIFY_TOKEN=apify_api_... python3 scripts/apify_verify_groundtruth.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

API_BASE = "https://api.apify.com/v2"
TOKEN = os.environ.get("APIFY_TOKEN", "").strip()


def fetch(url: str):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main() -> int:
    if not TOKEN:
        print("APIFY_TOKEN env required", file=sys.stderr)
        return 2
    listing = fetch(f"{API_BASE}/acts?my=true&token={TOKEN}&limit=100")
    items = listing.get("data", {}).get("items", [])
    print(f"total actors (list): {len(items)}")
    rows = []
    for it in items:
        aid = it["id"]
        d = fetch(f"{API_BASE}/acts/{aid}?token={TOKEN}").get("data", {})
        name = d.get("name") or it.get("name")
        desc_len = len(d.get("description") or "")
        readme_len = len(d.get("readme") or "")
        seo_title_len = len(d.get("seoTitle") or "")
        seo_desc_len = len(d.get("seoDescription") or "")
        cats = d.get("categories") or []
        is_public = d.get("isPublic")
        rows.append({
            "actor_id": aid,
            "name": name,
            "isPublic": is_public,
            "desc_len": desc_len,
            "readme_len": readme_len,
            "seoTitle_len": seo_title_len,
            "seoDesc_len": seo_desc_len,
            "cats_cnt": len(cats),
        })
        print(
            f"{'PUB' if is_public else 'prv'} {name}: desc={desc_len} "
            f"readme={readme_len} seoTitle={seo_title_len} "
            f"seoDesc={seo_desc_len} cats={len(cats)}"
        )

    # 基準チェック (成功指標: desc>=120, readme>=800, public)
    public = [r for r in rows if r["isPublic"]]
    nonpub = [r for r in rows if not r["isPublic"]]
    public_desc_ok = sum(1 for r in public if r["desc_len"] >= 120)
    public_readme_ok = sum(1 for r in public if r["readme_len"] >= 800)
    print("\n--- summary ---")
    print(f"public={len(public)} non_public={len(nonpub)}")
    print(f"public desc>=120: {public_desc_ok}/{len(public)}")
    print(f"public readme>=800: {public_readme_ok}/{len(public)}")
    print(f"public seoDesc>=80: {sum(1 for r in public if r['seoDesc_len'] >= 80)}/{len(public)}")
    print(f"public cats>0: {sum(1 for r in public if r['cats_cnt'] > 0)}/{len(public)}")

    out = "reports/apify-seo/apify-groundtruth-latest.json"
    os.makedirs("reports/apify-seo", exist_ok=True)
    with open(out, "w") as f:
        json.dump({"public": public, "non_public": nonpub}, f, ensure_ascii=False, indent=2)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
