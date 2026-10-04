#!/usr/bin/env python3
"""apify_store_opportunity — 需要×勝てるか でキーワード機会を並べる（読み取り専用）。

2026-10-03 の実測から:
  - 自社は順位が良いキーワードほど需要がゼロ（"japan used camera" は1位も自社も u30=1、
    "anime figure price" は1位が自社で u30=0）
  - 需要があるキーワード（"mercari japan"=1位がu30 29、"yahoo auctions japan"=7）では 18-20位
  - 説明文を直しても順位は ±0 だった（＝文言では順位は動かない）
  → 動かせるのは「需要のあるのに自社が出ていない/弱い」キーワードに入ること。それを探す。

需要の代理指標: Store 検索の上位5件の totalUsers30Days 合計（その語を使う側の実利用者数）。
圏外 = 深さ depth までに自社が出ない（＝語が本文に無い可能性が高い＝文言で入れる余地がある）。

使い方:
  python3 scripts/apify_store_opportunity.py
  python3 scripts/apify_store_opportunity.py --out reports/apify-seo/opportunity.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REPO = "/mnt/d/Project2/kensho"
API = "https://api.apify.com/v2"
OWN_USER = "fruitful_quintessence"

# 自社アセットから派生した候補語（サイト名×用途）
CANDIDATES = [
    "mercari japan", "yahoo auctions japan", "japan used camera", "anime figure price",
    "japan rent suumo", "japan real estate", "japan used watch", "japan luxury brand",
    "japan used instrument guitar", "mandarake", "dlsite", "japan kakaku price",
    "japan hotspot wifi", "japan hotel price", "japan train fare", "japan weather api",
    "japan corporate registry", "japan egov law", "japan wage data", "japan fuel price",
    "kimono resale", "golf club used japan", "fishing tackle japan", "japan smartphone used",
    "japan used motorcycle", "japan car price", "japan prize giveaway", "japan crowdfunding",
    "japan mcp server", "nendoroid price",
]


def get_token() -> str:
    env = {}
    try:
        with open(os.path.join(REPO, ".env"), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
                if m:
                    env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except OSError:
        pass
    for name in ("APIFY_TOKEN", "APIFY_TOKEN_DEFAULT"):
        val = (os.environ.get(name) or env.get(name) or "").strip()
        if val:
            return val
    return ""


def store(token: str, search: str, limit: int = 10, offset: int = 0) -> dict:
    q = urllib.parse.urlencode({"search": search, "limit": str(limit), "offset": str(offset)})
    req = urllib.request.Request(f"{API}/store?{q}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read()).get("data", {})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=100, help="自社を探す深さ")
    ap.add_argument("--out", default=os.path.join(REPO, "reports", "apify-seo", "opportunity.json"))
    args = ap.parse_args()

    token = get_token()
    if not token:
        print("ERROR: token 不在", flush=True)
        return 2

    rows = []
    for kw in CANDIDATES:
        try:
            top = store(token, kw, 10).get("items") or []
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {kw}: {type(exc).__name__}")
            continue
        demand = sum((a.get("stats") or {}).get("totalUsers30Days") or 0 for a in top[:5])
        top1 = (top[0].get("stats") or {}).get("totalUsers30Days") if top else None
        ours = None
        for off in (0, 100):
            try:
                items = store(token, kw, 100, off).get("items") or []
            except Exception:  # noqa: BLE001
                break
            for i, it in enumerate(items):
                if (it.get("username") or "") == OWN_USER:
                    ours = off + i + 1
                    break
            if ours or not items:
                break
        rows.append({
            "keyword": kw, "demand_top5_u30": demand, "top1_u30": top1,
            "top1_actor": (top[0].get("name") if top else None),
            "our_rank": ours, "our_present": ours is not None,
        })

    # 需要があり、かつ自社が弱い/不在のものを上位に
    rows.sort(key=lambda r: (-r["demand_top5_u30"], r["our_rank"] or 10**6))

    print(f"{'keyword':<28} {'需要(top5u30)':>12} {'当社順位':>8}  1位")
    for r in rows:
        rk = r["our_rank"]
        mark = " ←不在" if rk is None else (" ←弱い" if rk > 10 else "")
        print(f"{r['keyword']:<28} {r['demand_top5_u30']:>12} "
              f"{(str(rk) if rk else '圏外'):>8}  {r['top1_actor']}{mark}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "rows": rows},
                  fh, ensure_ascii=False, indent=1)
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
