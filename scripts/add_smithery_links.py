#!/usr/bin/env python3
"""Add Smithery install links to dev.to articles that don't have them yet.

Usage:
  python3 scripts/add_smithery_links.py --dry-run    # preview only
  python3 scripts/add_smithery_links.py --apply       # actually PATCH each article
"""
import json
import os
import re
import sys
import urllib.request

API = "https://dev.to/api/articles"
STORE_BASE = "https://apify.com/fruitful_quintessence"
SMITHERY_NS = "atushi1841"

# 記事の語 → (Smitheryサーバー名, Apifyアクター名, 説明) のマッピング
# 優先度順（上に高い）
SMITHERY_ROUTES: list[tuple[tuple[str, ...], tuple[str, str, str]]] = [
    # 懸賞・当選系
    (("懸賞", "当選", "giveaway", "sweepstake", "entry", "応募"),
     ("kensho-sweep-mcp", "japan-prize-giveaway-scraper", "Japan sweepstakes MCP server")),
    # 中古EC
    (("mercari", "メルカリ"),
     ("japan-ec-apify-mcp", "mercari-japan-search-scraper", "Japan EC MCP (Mercari/Yahoo/Rakuten)")),
    # 市場データ全般
    (("market", "価格", "price", "prices", "比較"),
     ("japan-market-mcp", "japan-market-mcp", "Japan market data MCP server")),
    # フィギュア
    (("figure", "フィギュア", "anime figure"),
     ("japan-anime-figure-mcp", "japan-anime-figure-price-data", "Japan anime figure price MCP")),
    # 最小賃金
    (("minimum wage", "最低賃金"),
     ("japan-minimum-wage-mcp", "japan-minimum-wage-mcp", "Japan minimum wage MCP")),
    # 燃料価格
    (("fuel", "ガソリン", "灯油"),
     ("japan-fuel-price-mcp", "japan-fuel-price-mcp", "Japan fuel price MCP")),
    # JEPX
    (("jepx", "電力", "電力市場"),
     ("japan-jepx-mcp", "japan-jepx-mcp", "Japan JEPX electricity MCP")),
]

SECTION_TITLE = "Install via Smithery"
SMITHERY_SECTION_TEMPLATE = """
---

## {title}

Get this server installed in your AI client (Claude Desktop, Cursor, VS Code, etc.) via Smithery:

```bash
npx @smithery/cli install {smithery_name} --client claude
```

Or browse the registry: https://smithery.ai/server/{ns}/{smithery_name}

> This is an MCP server that provides structured Japanese market data to AI agents.
"""


def get_key() -> str:
    env = {}
    try:
        with open("/mnt/d/Project2/kensho/.env", encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
                if m:
                    env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except OSError:
        pass
    for name in ("DEVTO_API_KEY", "DEVTO_KEY"):
        val = (os.environ.get(name) or env.get(name) or "").strip()
        if val:
            return val
    return ""


def call(method: str, path: str, key: str, body: dict | None = None) -> tuple[int, dict]:
    headers = {
        "api-key": key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    }
    req = urllib.request.Request(API + path, method=method, headers=headers)
    data = json.dumps(body).encode("utf-8") if body else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as resp:
            st = resp.status
            raw = resp.read().decode("utf-8")
            return st, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, {}


def pick_smithery(article: dict) -> tuple[str, str] | None:
    """Return (smithery_name, actor_slug) or None."""
    hay = ((article.get("title") or "") + " "
           + " ".join(article.get("tag_list") or []) + " "
           + (article.get("body_markdown") or "")).lower()
    for keys, (name, actor, _) in SMITHERY_ROUTES:
        if any(k in hay for k in keys):
            return name, actor
    return None


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--out", default="/tmp/smithery-links.json")
    args = ap.parse_args()

    key = get_key()
    if not key:
        print("ERROR: DEVTO_API_KEY が .env に無い", file=sys.stderr)
        return 2

    st, arts = call("GET", "/me/published?per_page=100", key)
    if st != 200 or not isinstance(arts, list):
        print(f"ERROR: 記事一覧取得失敗 status={st}", file=sys.stderr)
        return 1

    print(f"公開記事: {len(arts)}本")
    rows = []
    for a in arts:
        aid = a.get("id")
        title = a.get("title", "")
        body = a.get("body_markdown") or ""
        has_smithery = "smithery" in body.lower()
        smithery = pick_smithery(a)
        if not smithery:
            print(f"  対象外(id={aid}): {title[:60]}")
            continue
        sname, actor = smithery
        if has_smithery:
            print(f"  既存(id={aid}): {title[:60]} — Smithery linkあり")
            continue
        section = SMITHERY_SECTION_TEMPLATE.format(
            title=SECTION_TITLE,
            smithery_name=sname,
            ns=SMITHERY_NS,
        )
        new_body = body.rstrip() + "\n" + section
        row = {
            "id": aid, "title": title, "url": a.get("url"),
            "smithery": sname, "actor": actor,
            "added_chars": len(new_body) - len(body)
        }
        if args.apply:
            st2, _ = call("PUT", f"/{aid}", key, {"article": {"body_markdown": new_body}})
            st3, verify = call("GET", f"/{aid}", key)
            live = (verify.get("body_markdown") if isinstance(verify, dict) else "") or ""
            row["put_status"] = st2
            row["readback_ok"] = "smithery" in live.lower()
            print(f"     PUT id={aid} st={st2} readback={'OK' if row['readback_ok'] else 'FAIL'}")
        else:
            row["dry_run_preview"] = new_body[-300:]
            print(f"  [DRY-RUN] id={aid}: {title[:60]} → +{row['added_chars']}chars")
        rows.append(row)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"applied": bool(args.apply), "rows": rows}, fh, ensure_ascii=False, indent=1)
    print(f"\n結果: {len(rows)}件 → {args.out}")
    if not args.apply:
        print("(dry-run: 書き込みなし。--apply で反映)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
