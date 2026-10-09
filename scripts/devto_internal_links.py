#!/usr/bin/env python3
# Verified 2026-10-23: username matches atu_ino_ed473db24d76d234a
"""devto_internal_links — dev.to の公開済み記事に Apify Store への内部リンクを差し込む。

なぜやるか（2026-10-03 の実測より）:
  Apify Store 内のSEOは上限が低い（最大需要のキーワードでも上位5件合計 50人/月、
  文言を直しても順位は ±0位）。伸ばせるのは「外から人を連れる」導線だけ。
  dev.to の記事は生存確認済み（HTTP 200）なので、ここから Store ページへ送るのが最短。

前提:
  .env に DEVTO_API_KEY が必要。無い場合は終了コード2で即失敗する（偽の成功を返さない）。

使い方:
  python3 scripts/devto_internal_links.py --dry-run     # 差分を見るだけ
  python3 scripts/devto_internal_links.py --apply       # 実際に PUT して差し込む
  python3 scripts/devto_internal_links.py --list        # 自分の公開記事一覧と既存リンク数

設計:
  - 記事タイトル/タグに含まれる語から、対応する Store アクターを決め打ち表で選ぶ
  - 既に Store リンクがある記事は触らない（冪等）
  - 末尾に "Data used in this post" 節を追記するだけ（本文は書き換えない＝破壊しない）
  - PUT 後に再取得して反映を確認する（read-back）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO = "/mnt/d/Project2/kensho"
API = "https://dev.to/api/articles"
STORE_BASE = "https://apify.com/fruitful_quintessence"

# 記事の語 → Store アクター名（slug）。上から順に最初に当たったものを採用。
ROUTES: list[tuple[tuple[str, ...], list[str]]] = [
    # 懸賞・当選系（2026-10-03 追加: 懸賞記事3本がリンク0本で放置されていた）
    (("懸賞", "当選", "giveaway", "sweepstake"), ["japan-prize-giveaway-scraper"]),
    (("mercari",), ["mercari-japan-search-scraper"]),
    (("yahoo auction", "オークション", "auction"), ["yahoo-auctions-japan-scraper", "mandarake-auction-scraper"]),
    (("camera", "カメラ"), ["japan-used-camera-market-scraper", "kitamura-japan-used-camera-scraper"]),
    (("watch", "時計"), ["japan-watch-market-scraper", "jackroad-used-watch-scraper"]),
    (("anime", "figure", "フィギュア"), ["japan-anime-figure-price-data", "surugaya-japan-hobby-prices"]),
    (("instrument", "guitar", "楽器"), ["japan-used-instrument-market-scraper", "digimart-japan-used-instrument-scraper"]),
    (("rent", "real estate", "賃貸", "不動産"), ["japan-rent-market-scraper", "suumo-japan-real-estate-scraper"]),
    # MLIT不動産取引価格 (2026-10-07 追加: t_f5f6f8a9/t_51c711a9対応)
    (("property", "不動産", "mlit", "real estate transaction", "land price", "物件価格"),
     ["mlit-japan-property-prices"]),
    (("price", "prices", "価格"), ["japan-kakaku-price-search", "japan-market-mcp"]),
]

SECTION_TITLE = "Data used in this post"


def get_key() -> str:
    env = {}
    try:
        with open(os.path.join(REPO, ".env"), encoding="utf-8") as fh:
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


def call(method: str, path: str, key: str, body: dict | None = None) -> tuple[int, dict | list]:
    req = urllib.request.Request(
        API + path, method=method,
        headers={"api-key": key, "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:  # noqa: BLE001
            return e.code, {}


def pick_actors(article: dict) -> list[str]:
    hay = ((article.get("title") or "") + " " + " ".join(article.get("tag_list") or []) + " " + (article.get("body_markdown") or "")).lower()
    matched: list[str] = []
    for keys, actors in ROUTES:
        if any(k in hay for k in keys):
            for a in actors:
                if a not in matched:
                    matched.append(a)
    return matched


def build_section(actors: list[str]) -> str:
    lines = ["", "---", "", f"## {SECTION_TITLE}", "",
             "The datasets behind this analysis are available on Apify (pay-per-result, free tier to start):", ""]
    for a in actors:
        lines.append(f"- [{a}]({STORE_BASE}/{a}?utm_source=devto&utm_medium=article&utm_campaign=weekly_seo)")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out", default=os.path.join(REPO, "reports", "apify-seo", "devto-links.json"))
    args = ap.parse_args()

    key = get_key()
    if not key:
        print("ERROR: DEVTO_API_KEY が .env に無い。dev.to の Settings > Extensions で発行して "
              ".env に DEVTO_API_KEY=... を追加してから再実行する。", file=sys.stderr)
        return 2

    st, arts = call("GET", "/me/published?per_page=100", key)
    if st != 200 or not isinstance(arts, list):
        print(f"ERROR: 記事一覧の取得に失敗 status={st}", file=sys.stderr)
        return 1

    print(f"公開記事: {len(arts)}本")
    rows = []
    for a in arts:
        aid, title = a.get("id"), a.get("title")
        body = a.get("body_markdown") or ""
        actors = pick_actors(a)
        if not actors:
            print(f"  対象外 id={aid} {title[:58]}")
            continue
        # 既に全アクターのlinkが存在するか（部分的でも可: 一部のみなら追加）
        existing = [a2 for a2 in actors if f"{STORE_BASE}/{a2}" in body]
        if len(existing) == len(actors):
            print(f"  既存 id={aid} {title[:58]}")
            continue
        missing = [a2 for a2 in actors if a2 not in existing]
        new_body = body.rstrip() + "\n" + build_section(missing)
        rows.append({"id": aid, "title": title, "url": a.get("url"), "actors": actors,
                     "missing_actors": missing,
                     "added_chars": len(new_body) - len(body)})
        if args.apply:
            st2, resp = call("PUT", f"/{aid}", key, {"article": {"body_markdown": new_body}})
            st3, verify = call("GET", f"/{aid}", key)
            live = (verify.get("body_markdown") if isinstance(verify, dict) else "") or ""
            rows[-1].update({"put_status": st2, "readback_has_link":
                             all(f"{STORE_BASE}/{a2}" in live for a2 in actors)})
            print(f"     PUT {st2} / read-back 反映={rows[-1]['readback_has_link']}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"applied": bool(args.apply), "rows": rows}, fh, ensure_ascii=False, indent=1)
    print(f"\n追記対象: {len(rows)}本  -> {args.out}")
    if not args.apply:
        print("（--dry-run のため書き込みなし。--apply で反映）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
