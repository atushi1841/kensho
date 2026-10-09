#!/usr/bin/env python3
"""publish_devto — dev.to 下書き Markdown を dev.to API で投稿する。

publish_qiita.py と同一設計:
  - front matter (title/tags/published) を読み取り、本文から投稿ペイロードを組み立てる
  - 既定は dry-run（投稿しない）。実際に投稿するには --publish を付ける
  - トークンは環境変数 DEVTO_API_KEY、無ければ <repo>/.env から読む

使い方:
  python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W40.md
  python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W40.md --publish
  python3 scripts/publish_devto.py FILE --publish --public

設計メモ:
  - dev.to API は PUT /api/articles/<id> で更新、POST /api/articles で新規作成
  - 既存の8本は devto_internal_links.py で内部リンク差し込み済み（API経由PUT）
  - 本スクリプトは新規記事（W39/W40）の初回投稿専用。下書きの front matter に
    published: false が付いている場合は draft として投稿（--public で上書き可）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://dev.to/api/articles"
MAX_TAGS = 4  # dev.to は最大4タグ


def load_token(repo_root: Path) -> str | None:
    tok = os.environ.get("DEVTO_API_KEY")
    if tok:
        return tok.strip()
    env_path = repo_root / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("DEVTO_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _coerce(value: str) -> object:
    v = value.strip()
    if v in ("true", "false"):
        return v == "true"
    return v.strip('"').strip("'")


def parse_draft(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    meta: dict = {"tags": []}
    body = raw
    fm = None
    if raw.startswith("---\n") or raw.startswith("---\r\n"):
        end = raw.find("\n---", 4)
        if end != -1:
            fm = raw[4:end]
            body = raw[end + 4 :].lstrip("\r\n")
    else:
        header, sep, rest = raw.partition("\n\n")
        if sep and re.match(r"^(title|tags|published)\s*:", header.strip()):
            fm = header
            body = rest.lstrip("\r\n")
    if fm is not None:
        in_tags = False
        for line in fm.splitlines():
            if re.match(r"^\s*-\s+", line) and in_tags:
                meta["tags"].append(re.sub(r"^\s*-\s+", "", line).strip())
                continue
            in_tags = False
            if ":" in line:
                key, _, val = line.partition(":")
                key, val = key.strip(), val.strip()
                if key == "tags" and not val:
                    in_tags = True
                    continue
                meta[key] = _coerce(val) if val else ""
    # 先頭の重複 H1 を除去
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if line.strip() == f"# {meta.get('title', '')}".strip():
            lines = lines[i + 1 :]
        break
    return meta, "\n".join(lines).strip() + "\n"


def normalize_title(title: str) -> str:
    """デデアップ用: 小文字化+空白正規化したタイトル。"""
    return " ".join(title.strip().lower().split())


def find_existing_articles(token: str, title: str) -> list[dict]:
    """自分の投稿（published+draft）から正規化タイトル一致の既存記事を探す。
    GET /api/articles/me → [{id, page_views_count, published}, ...]（無ければ []）。"""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        "https://dev.to/api/articles/me?per_page=100",
        headers={"api-key": token, "User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            arts = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"[WARN] 既存記事取得失敗 HTTP {e.code} — デデアップゲートスキップ", file=sys.stderr)
        return []
    target = normalize_title(title)
    hits = []
    for a in arts:
        a = a.get("article", a)
        if normalize_title(a.get("title", "")) == target:
            hits.append(a)
    return hits


def pick_canonical(hits: list[dict]) -> dict:
    """canonical = views最大、同数なら最古（id最小）。viewをここに集中させる。"""
    return max(hits, key=lambda a: (int(a.get("page_views_count") or 0), -int(a.get("id") or 0)))


def update_article(token: str, article_id: int, payload: dict) -> dict:
    """PUT /api/articles/<id> で既存記事を更新（createしない）。"""
    import urllib.request

    req = urllib.request.Request(
        f"{API}/{article_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def build_payload(meta: dict, body: str, force_public: bool) -> dict:
    tags = (meta.get("tags") or [])[:MAX_TAGS]
    published = True if force_public else bool(meta.get("published", False))
    return {
        "article": {
            "title": meta.get("title", "").strip() or "(no title)",
            "body_markdown": body,
            "tags": tags,
            "published": published,
        }
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", type=Path)
    ap.add_argument("--publish", action="store_true", help="実際に投稿する（既定は dry-run）")
    ap.add_argument("--public", action="store_true", help="published:false を無視して公開")
    args = ap.parse_args()

    draft = args.draft if args.draft.is_absolute() else repo_root / args.draft
    if not draft.is_file():
        print(f"[ERR] draft not found: {draft}", file=sys.stderr)
        return 2

    meta, body = parse_draft(draft)
    payload = build_payload(meta, body, args.public)
    print(f"[DRAFT] {draft}")
    print(f"[META ] title={payload['article']['title']!r} tags={payload['article']['tags']} published={payload['article']['published']}")
    print(f"[BODY ] {len(payload['article']['body_markdown'])} chars, {payload['article']['body_markdown'].count(chr(10))} lines")
    for pat in ("（データ不足）", "TODO", "XXX", "{{", "}}"):
        if pat in payload["article"]["body_markdown"]:
            print(f"[WARN ] placeholder-ish token in body: {pat!r}")

    if not args.publish:
        print("[DRY-RUN] --publish 未指定のため投稿しません")
        return 0

    token = load_token(repo_root)
    if not token:
        print("[ERR] DEVTO_API_KEY が未設定（env / .env）", file=sys.stderr)
        return 3

    # デデアップゲート: 正規化タイトル一致の既存記事があれば POST せず PUT で更新する
    existing = find_existing_articles(token, payload["article"]["title"])
    if existing:
        canonical = pick_canonical(existing)
        cid = int(canonical["id"])
        print(f"[DEDUP] 既存記事 {len(existing)}件検出 (ids={[a['id'] for a in existing]}) → canonical id={cid} をPUT更新します")
        try:
            data = update_article(token, cid, payload)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            print(f"[ERR] PUT HTTP {e.code}: {detail}", file=sys.stderr)
            return 4
        except Exception as e:
            print(f"[ERR] PUT {type(e).__name__}: {e}", file=sys.stderr)
            return 5
        art = data.get("article", data)
        print(f"[OK] {art.get('url')} (id={art.get('id')}, published={art.get('published')}) [updated, not created]")
        return 0

    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        print(f"[ERR] HTTP {e.code}: {detail}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"[ERR] {type(e).__name__}: {e}", file=sys.stderr)
        return 5

    art = data.get("article", data)
    print(f"[OK] {art.get('url')} (id={art.get('id')}, published={art.get('published')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())