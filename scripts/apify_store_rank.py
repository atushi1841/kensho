#!/usr/bin/env python3
"""apify_store_rank — Apify Store 検索での自社アクター順位を測る（読み取り専用）。

なぜ必要か（2026-10-03）:
  「Store SEO が死んでいる」という判定が過去に2回誤って出た。どちらも API の読み違いだった。
    - /v2/acts の isPublic を信用した（実際は 78/88 が公開）
    - 無認証の /v2/store は count は返すが items=[]（仕様）
  推測をやめ、**検索結果の中での実際の順位**を毎回実測して前後比較する。

使い方:
  python3 scripts/apify_store_rank.py                        # 既定キーワード
  python3 scripts/apify_store_rank.py --keywords "japan used camera,mercari japan"
  python3 scripts/apify_store_rank.py --out reports/apify-seo/rank-before.json
  python3 scripts/apify_store_rank.py --compare reports/apify-seo/rank-before.json

出力: キーワードごとに「自社最上位の順位 / アクター名 / 上位3件の顔ぶれ」
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REPO = "/mnt/d/Project2/kensho"
API = "https://api.apify.com/v2"
OWN_USER = "fruitful_quintessence"

DEFAULT_KEYWORDS = [
    "mercari japan",
    "yahoo auctions japan",
    "japan used camera",
    "anime figure price",
    "japan rent suumo",
    "mandarake",
    "japan watch price",
    "japan hotel",
]


def get_token() -> str:
    """絶対パスの .env から読む（cron の cwd が違っても効く）。"""
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


def store_page(token: str, search: str, offset: int, limit: int, sort: str | None) -> dict:
    q = {"search": search, "limit": str(limit), "offset": str(offset)}
    if sort:
        q["sortBy"] = sort
    url = f"{API}/store?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def best_rank(token: str, keyword: str, depth: int = 200, sort: str | None = None) -> dict:
    """キーワードで検索し、自社アクターの最上位順位を返す（1始まり）。"""
    seen_total = None
    found: dict | None = None
    offset = 0
    while offset < depth:
        try:
            data = store_page(token, keyword, offset, 100, sort)["data"]
        except Exception as exc:  # noqa: BLE001
            return {"keyword": keyword, "sort": sort, "error": f"{type(exc).__name__}: {exc}"}
        seen_total = data.get("count")
        items = data.get("items") or []
        if not items:
            break
        for i, it in enumerate(items):
            if (it.get("username") or "") == OWN_USER:
                found = {
                    "rank": offset + i + 1,
                    "name": it.get("name"),
                    "title": (it.get("title") or "")[:70],
                    "users30d": ((it.get("stats") or {}).get("totalUsers30Days")),
                    "runs": ((it.get("stats") or {}).get("totalRuns")),
                }
                break
        if found:
            break
        offset += len(items)
    top = []
    try:
        for i, it in enumerate((store_page(token, keyword, 0, 3, sort)["data"].get("items") or [])):
            top.append({
                "rank": i + 1,
                "name": it.get("name"),
                "user": it.get("username"),
                "users30d": (it.get("stats") or {}).get("totalUsers30Days"),
            })
    except Exception:  # noqa: BLE001
        pass
    return {
        "keyword": keyword,
        "sort": sort,
        "total_matches": seen_total,
        "our_best_rank": (found or {}).get("rank"),
        "our_actor": (found or {}).get("name"),
        "our_title": (found or {}).get("title"),
        "our_users30d": (found or {}).get("users30d"),
        "top3": top,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", default=",".join(DEFAULT_KEYWORDS))
    ap.add_argument("--depth", type=int, default=200, help="何位まで探すか")
    ap.add_argument("--out", default=os.path.join(REPO, "reports", "apify-seo", "rank-latest.json"))
    ap.add_argument("--compare", default=None, help="過去の出力と比較する")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    token = get_token()
    if not token:
        print("ERROR: APIFY_TOKEN(.env の APIFY_TOKEN_DEFAULT) が見つからない", file=sys.stderr)
        return 2

    kws = [k.strip() for k in args.keywords.split(",") if k.strip()]
    rows = []
    print(f"{'keyword':<24} {'total':>6} {'自社順位':>8}  actor")
    for kw in kws:
        r = best_rank(token, kw, args.depth)
        rows.append(r)
        rank = r.get("our_best_rank")
        print(f"{kw:<24} {str(r.get('total_matches')):>6} {str(rank if rank else '圏外'):>8}  "
              f"{r.get('our_actor') or r.get('error') or '-'}")

    out = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "depth": args.depth,
        "own_user": OWN_USER,
        "rows": rows,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"\n-> {args.out}")

    if args.compare and os.path.exists(args.compare):
        with open(args.compare, encoding="utf-8") as fh:
            prev = json.load(fh)
        before = {r["keyword"]: r.get("our_best_rank") for r in prev.get("rows", [])}
        print(f"\n{'keyword':<24} {'before':>8} {'after':>8}  差")
        for r in rows:
            b = before.get(r["keyword"])
            a = r.get("our_best_rank")
            if b is None and a is None:
                d = "圏外のまま"
            elif b is None:
                d = f"新規 {a}位"
            elif a is None:
                d = "圏外に落ちた"
            else:
                d = f"{b - a:+d}位"
            print(f"{r['keyword']:<24} {str(b or '圏外'):>8} {str(a or '圏外'):>8}  {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
