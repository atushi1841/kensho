#!/usr/bin/env python3
"""Qiita 下書き Markdown を Qiita API v2 で投稿する。

- front matter (title / tags / private) を読み取り、本文から投稿ペイロードを組み立てる。
- 既定は dry-run（投稿しない）。実際に投稿するには --publish を付ける。
- トークンは環境変数 QIITA_TOKEN、無ければ <repo>/.env から読む（値をログに出さない）。

使い方:
  python3 scripts/publish_qiita.py reports/journalism/drafts/qiita-2026W40.md            # dry-run
  python3 scripts/publish_qiita.py reports/journalism/drafts/qiita-2026W40.md --publish  # 本番投稿
  python3 scripts/publish_qiita.py FILE --publish --public   # private:true を上書きして公開
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

API = "https://qiita.com/api/v2/items"
MAX_TAGS = 5


def load_token(repo_root: Path) -> str | None:
    tok = os.environ.get("QIITA_TOKEN")
    if tok:
        return tok.strip()
    env_path = repo_root / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("QIITA_TOKEN="):
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
    fm = None  # front matter 本文（フェンス無しにも対応）
    if raw.startswith("---\n") or raw.startswith("---\r\n"):
        end = raw.find("\n---", 4)
        if end != -1:
            fm = raw[4:end]
            body = raw[end + 4 :].lstrip("\r\n")
    else:
        # kensho_data_journalism.py は `---` フェンス無しで title/tags/private を先頭に置く
        header, sep, rest = raw.partition("\n\n")
        if sep and re.match(r"^(title|tags|private)\s*:", header.strip()):
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
    # 先頭の重複 H1 を除去（Qiita はタイトルを別フィールドで持つため）
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if line.strip() == f"# {meta.get('title', '')}".strip():
            lines = lines[i + 1 :]
        break
    return meta, "\n".join(lines).strip() + "\n"


def build_payload(meta: dict, body: str, force_public: bool) -> dict:
    tags = [{"name": t, "versions": []} for t in (meta.get("tags") or [])][:MAX_TAGS]
    private = False if force_public else bool(meta.get("private", True))
    return {
        "title": meta.get("title", "").strip() or "(no title)",
        "body": body,
        "tags": tags,
        "private": private,
        "coediting": False,
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", type=Path)
    ap.add_argument("--publish", action="store_true", help="実際に投稿する（既定は dry-run）")
    ap.add_argument("--public", action="store_true", help="private:true を無視して公開する")
    args = ap.parse_args()

    draft = args.draft if args.draft.is_absolute() else repo_root / args.draft
    if not draft.is_file():
        print(f"[ERR] draft not found: {draft}", file=sys.stderr)
        return 2

    meta, body = parse_draft(draft)
    payload = build_payload(meta, body, args.public)
    print(f"[DRAFT] {draft}")
    print(f"[META ] title={payload['title']!r} tags={[t['name'] for t in payload['tags']]} private={payload['private']}")
    print(f"[BODY ] {len(payload['body'])} chars, {payload['body'].count(chr(10))} lines")
    for pat in ("（データ不足）", "TODO", "XXX", "{{", "}}"):
        if pat in payload["body"]:
            print(f"[WARN ] placeholder-ish token in body: {pat!r}")

    if not args.publish:
        print("[DRY-RUN] --publish 未指定のため投稿しません")
        return 0

    token = load_token(repo_root)
    if not token:
        print("[ERR] QIITA_TOKEN が未設定（env / .env）", file=sys.stderr)
        return 3

    import time
    import urllib.error
    import urllib.request

    max_retries = 5
    data: dict = {}
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            API,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
                break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                wait = min(15 * (2 ** attempt), 120)
                print(f"[WAIT] 429 rate-limited — retry in {wait}s (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(wait)
                continue
            detail = e.read().decode("utf-8", "replace")[:500]
            print(f"[ERR] HTTP {e.code}: {detail}", file=sys.stderr)
            return 4
        except Exception as e:  # noqa: BLE001
            print(f"[ERR] {type(e).__name__}: {e}", file=sys.stderr)
            return 5

    print(f"[OK] {data.get('url')} (id={data.get('id')}, private={data.get('private')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
