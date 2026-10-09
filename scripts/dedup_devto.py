#!/usr/bin/env python3
"""dedup_devto — dev.to の同一タイトル重複記事を整理する（t_957e7220）。

- GET /api/articles/me で全投稿を取得
- タイトル正規化（小文字化+空白圧縮）でグループ化
- canonical = views最大・同数なら最古（id最小）を保持
- それ以外は DELETE /api/articles/{id} で削除
- --dry-run 既定。削除には --apply 必須。

使い方:
  python3 scripts/dedup_devto.py            # 棚卸し（削除しない）
  python3 scripts/dedup_devto.py --apply    # 削除実行
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish_devto import API, find_existing_articles, load_token, normalize_title  # noqa: E402


def delete_article(token: str, article_id: int) -> bool:
    req = urllib.request.Request(
        f"{API}/{article_id}",
        headers={"api-key": token, "User-Agent": "Mozilla/5.0"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        print(f"[WARN] DELETE {article_id} failed: HTTP {e.code}", file=sys.stderr)
        return False


def unpublish_article(token: str, article_id: int) -> bool:
    """dev.to API に DELETE は存在しない（実測404）ため、PUT published:false で
    非公開化して view 集中化を実現する（t_957e7220 実測: 非公開化は有効）。"""
    req = urllib.request.Request(
        f"{API}/{article_id}",
        data=json.dumps({"article": {"published": False}}).encode("utf-8"),
        headers={"api-key": token, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        print(f"[WARN] UNPUBLISH {article_id} failed: HTTP {e.code}", file=sys.stderr)
        return False


def remove_duplicate(token: str, article_id: int) -> str:
    """dev.to APIにはDELETEが存在しない（実測: DELETE→404、t_957e7220）ため、
    PUT published:false で非公開化する。dev.to APIはレート制限が厳しい
    （実測: 連続PUTで429）ため試行間にsleep+リトライする。"""
    import time
    time.sleep(3)
    for attempt in range(4):
        if unpublish_article(token, article_id):
            return "unpublished"
        print(f"[WAIT] 429対策: {30*(attempt+1)}s wait", file=sys.stderr)
        time.sleep(30 * (attempt + 1))
    return "delete_failed"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="実際に削除する（既定は dry-run）")
    args = ap.parse_args()

    token = load_token(repo_root)
    if not token:
        print("[ERR] DEVTO_API_KEY が未設定", file=sys.stderr)
        return 3

    req = urllib.request.Request(
        "https://dev.to/api/articles/me?per_page=100",
        headers={"api-key": token, "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        arts = [a.get("article", a) for a in json.load(r)]

    groups: dict[str, list[dict]] = defaultdict(list)
    for a in arts:
        groups[normalize_title(a.get("title", ""))].append(a)

    ledger = []
    deleted = 0
    for title, grp in groups.items():
        if len(grp) < 2:
            continue
        canonical = max(grp, key=lambda a: (int(a.get("page_views_count") or 0), -int(a.get("id") or 0)))
        print(f"[GROUP] x{len(grp)} keep={canonical['id']}(views={canonical.get('page_views_count')}) : {title[:60]}")
        for a in grp:
            if a["id"] == canonical["id"]:
                continue
            action = "skip(dry-run)"
            if args.apply:
                action = remove_duplicate(token, int(a["id"]))
                if action in ("deleted", "unpublished"):
                    deleted += 1
            print(f"    - id={a['id']} views={a.get('page_views_count')} -> {action}")
            ledger.append({"title": title, "id": a["id"], "views": a.get("page_views_count"), "action": action, "canonical": canonical["id"]})

    print(f"[SUMMARY] groups={sum(1 for g in groups.values() if len(g) > 1)} deleted={deleted} apply={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
