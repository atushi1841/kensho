#!/usr/bin/env python3
"""actor_promo_inject — 上位PPEアクターのApify Storeリンクを記事に注入する。

外部流入促進: t_427357f6
- dev.to・Qiita の週次下書き（W43）にApify Store PPE actor リンクを自動埋め込み
- 既存リンクありの記事はスキップ（冪等）
- --apply で実際にファイルを書き戻す

上位PPE actor（2026-10-03 data/actor_priority_analysisより）:
  1. mandarake-auction-scraper       price=0.35  runs=324
  2. japan-offmall-market-scraper    price=0.002 runs=312
  3. tackleberry-japan-fishing-tackle price=0.002 runs=209
  4. mercari-japan-search-scraper    price=0.002 runs=152
  5. japan-used-camera-market-scraper price=0.002 runs=129

成功指標: external_users >= 1 / external_runs >= 5（30日以内）
検証コマンド: curl -s https://api.apify.com/v2/acts/<ID>/storeInfo
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path("/mnt/d/Project2/kensho")
STORE_BASE = "https://apify.com/fruitful_quintessence"

# 上位5 PPE actor（price > 0 で total_runs 降順）
TOP_ACTORS: list[tuple[str, str]] = [
    ("mandarake-auction-scraper", "q2E37PVTg5JcGOTEn"),
    ("japan-offmall-market-scraper", "Zh4kqcS4dYPWpFzBd"),
    ("tackleberry-japan-fishing-tackle-scraper", "wxMskoiHMPeeH2qAJ"),
    ("mercari-japan-search-scraper", "whSePszWpMtfeLYBp"),
    ("japan-used-camera-market-scraper", "mQaZFo6up4YZKepC3"),
]

# 記事本文の語句 → actor slug（複数マッチ時は先に定義された方が優先）
ROUTES: list[tuple[tuple[str, ...], str]] = [
    (("mercari", "メルカリ"), "mercari-japan-search-scraper"),
    (("オークション", "auction", "mandarake"), "mandarake-auction-scraper"),
    (("offmall", "ハードオフ", "オフモール"), "japan-offmall-market-scraper"),
    (("camera", "カメラ", "写植"), "japan-used-camera-market-scraper"),
    (("fishing", "釣具", "タックル"), "tackleberry-japan-fishing-tackle-scraper"),
]


def pick_actors(text: str) -> list[str]:
    hay = text.lower()
    seen: set[str] = set()
    for keys, slug in ROUTES:
        if any(k in hay for k in keys) and slug not in seen:
            seen.add(slug)
            return [slug]
    # fallback: 全部返す
    return [a[0] for a in TOP_ACTORS]


def section(actors: list[str], platform: str) -> str:
    label = "Data used in this post" if platform == "devto" else "関連ツール"
    lines = ["", "---", "", f"## {label}", ""]
    for slug in actors:
        lines.append(f"- [{slug}]({STORE_BASE}/{slug})")
    lines.append("")
    return "\n".join(lines)


def process_file(path: Path, platform: str, apply: bool) -> dict:
    body = path.read_text(encoding="utf-8", errors="replace")
    has_link = "apify.com/fruitful_quintessence" in body
    actors = pick_actors(body) if not has_link else []

    if has_link:
        return {"path": str(path), "status": "skip_existing", "actors": []}

    new_body = body.rstrip() + "\n" + section(actors, platform)
    if not apply:
        return {
            "path": str(path),
            "status": "dry_run",
            "actors": actors,
            "added_chars": len(new_body) - len(body),
        }

    path.write_text(new_body, encoding="utf-8")
    return {
        "path": str(path),
        "status": "applied",
        "actors": actors,
        "added_chars": len(new_body) - len(body),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="既定は dry-run。実際に書き戻すには --apply")
    ap.add_argument("--files", nargs="*", help="対象ファイルパス（指定なければデフォルト位置から自動検出）")
    args = ap.parse_args()

    if args.dry_run and not args.apply:
        pass  # dry-run mode
    elif args.apply:
        pass  # apply mode

    if not args.files:
        # 自動検出: W43 以下のドラフトを収集
        drafts = sorted(REPO.glob("reports/journalism/drafts/qiita-2026W4*.md"))
        drafts += sorted(REPO.glob("reports/journalism/drafts/devto-2026W4*.md"))
        files = [(p, "qiita" if p.stem.startswith("qiita") else "devto") for p in drafts]
    else:
        files = [(Path(p), "devto" if "devto" in p.lower() else "qiita") for p in args.files]

    results = []
    for path, platform in files:
        if not path.is_file():
            print(f"[SKIP] not found: {path}", file=sys.stderr)
            continue
        r = process_file(path, platform, apply=args.apply)
        results.append(r)
        status_icon = {"skip_existing": "→", "dry_run": "△", "applied": "✓"}[r["status"]]
        print(f"{status_icon} {path.name} | {r['status']} | actors={r['actors']}")

    # 要約
    n_skip = sum(1 for r in results if r["status"] == "skip_existing")
    n_apply = sum(1 for r in results if r["status"] == "applied")
    n_dry = sum(1 for r in results if r["status"] == "dry_run")
    print(f"\n合計: {len(results)} 件中 skip={n_skip} dry_run={n_dry} applied={n_apply}")
    if not args.apply:
        print("（--apply を付けて再実行すると実際のファイル書き戻しを行います）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
