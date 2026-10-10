#!/usr/bin/env python3
"""Qiita UTM Injection — add ?utm_source=qiita to apify.com links in existing articles.

Target: atushi1841's Qiita articles that contain apify.com links but lack utm_source=qiita.
Method: GET /api/v2/users/<user>/items → PATCH /api/v2/items/<id> with body updated.
Rate limit: 1 request / 10s per item (Qiita API v2 authenticated).

Exit codes:
  0 = at least one PATCH succeeded
  1 = candidates found but all PATCHes failed (or token invalid)
  2 = no candidates / token missing
  3 = token invalid (401/403)

Uses QIITA_TOKEN from /mnt/d/Project2/kensho/.env (never logged).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API_ITEMS = "https://qiita.com/api/v2/items"
USER = "atushi1841"
ENV_FILE = "/mnt/d/Project2/kensho/.env"
UTM = "?utm_source=qiita&utm_medium=article&utm_campaign=weekly_seo"
# apify.com links that already have a query string get & appended
LINK_RE = re.compile(r'https?://(?:www\.)?apify\.com(?:/[^\s"\'<>]*)?')


def load_token():
    tok = os.environ.get("QIITA_TOKEN", "")
    if tok:
        return tok
    for line in open(ENV_FILE, encoding="utf-8"):
        if line.startswith("QIITA_TOKEN="):
            return line.split("=", 1)[1].strip()
    return ""


def api_get(token, url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, {"error": str(e)}


def api_patch(token, item_id, body, tags=None, title=None, private=True):
    """PATCH /api/v2/items/{id} — Qiita API requires body+tags+title+private (body-only = 400)."""
    url = f"{API_ITEMS}/{item_id}"
    payload = {"body": body}
    if tags is not None:
        payload["tags"] = tags
    if title is not None:
        payload["title"] = title
    payload["private"] = private
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PATCH", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, {"error": str(e)}


def inject_utm(body):
    """Replace apify.com links that lack utm_source=qiita with UTM-tagged versions."""
    def repl(m):
        link = m.group(0)
        if "utm_source=qiita" in link:
            return link
        sep = "&" if "?" in link else "?"
        return link + sep + "utm_source=qiita&utm_medium=article&utm_campaign=weekly_seo"
    return LINK_RE.sub(repl, body)


def main():
    token = load_token()
    if not token:
        print("[ERR] QIITA_TOKEN not found", file=sys.stderr)
        return 2

    status, items = api_get(token, f"https://qiita.com/api/v2/users/{USER}/items?per_page=50")
    if status != 200 or not items:
        print(f"[ERR] GET items failed status={status}", file=sys.stderr)
        return 3 if status in (401, 403) else 1

    targets = []
    for a in items:
        body = a.get("body", "")
        if "apify.com" in body and "utm_source=qiita" not in body:
            targets.append((a["id"], a.get("title", ""), inject_utm(body),
                            a.get("tags", []), a.get("title", ""), a.get("private", True)))

    if not targets:
        print("[OK] no candidates — all apify.com links already have utm_source=qiita")
        return 0

    print(f"[INFO] {len(targets)} candidates")
    success = 0
    for i, (item_id, title, new_body, tags, ttl, priv) in enumerate(targets):
        print(f"[{i+1}/{len(targets)}] PATCH {item_id} ({title[:40]}) ...", end=" ", flush=True)
        st, resp = api_patch(token, item_id, new_body, tags=tags, title=ttl, private=priv)
        if st == 200:
            print(f"OK (HTTP {st})")
            success += 1
        else:
            print(f"FAIL HTTP {st} {resp}")
        if i < len(targets) - 1:
            time.sleep(10)  # Qiita rate limit

    print(f"[RESULT] PATCH {success}/{len(targets)}")
    return 0 if success == len(targets) else (3 if success == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())