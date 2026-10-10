#!/usr/bin/env python3
"""Patch Qiita article 897f8d90b1be3514d0b8: add apify.com links with UTM.

Replaces bare actor names in the table's first column with markdown links
pointing to the author's Apify store, adding utm_source=qiita for tracking.

Exit codes:
  0 = PATCH succeeded (1/1)
  1 = PATCH failed
  2 = token missing / API error
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

API_ITEMS = "https://qiita.com/api/v2/items"
ITEM_ID = "897f8d90b1be3514d0b8"
OWNER = "fruitful_quintessence"
UTM = "utm_source=qiita&utm_medium=article&utm_campaign=weekly_seo"
ENV_FILE = "/mnt/d/Project2/kensho/.env"

ACTORS = [
    "mercari-japan-search-scraper",
    "yahoo-auctions-japan-scraper",
    "japan-kakaku-price-search",
    "suumo-japan-real-estate-scraper",
    "japan-market-mcp",
    "rakuten-japan-mcp",
    "mercari-japan-scraper",
    "japan-prize-giveaway-scraper",
]


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
    url = f"{API_ITEMS}/{item_id}"
    payload = {"body": body}
    if tags is not None:
        payload["tags"] = tags
    if title is not None:
        payload["title"] = title
    payload["private"] = private
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PATCH", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, {"error": str(e)}


def build_new_body(body, actors):
    """Replace bare actor names in table cells with linked versions."""
    def repl(m):
        name = m.group(1)
        if name in actors:
            url = f"https://apify.com/{OWNER}/{name}?{UTM}"
            return f"[{name}]({url})"
        return m.group(0)
    # Match actor name inside table cell pipes: | name | ...
    pattern = r"\|\s*(" + "|".join(re.escape(a) for a in actors) + r")\s*\|"
    new_body = re.sub(pattern, repl, body)
    return new_body


def count_apify_links(body):
    return len(re.findall(rf"https://apify\.com/{re.escape(OWNER)}/", body))


def main():
    token = load_token()
    if not token:
        print("[ERR] QIITA_TOKEN not found", file=sys.stderr)
        return 2

    # GET current article
    st, item = api_get(token, f"{API_ITEMS}/{ITEM_ID}")
    if st != 200 or not item:
        print(f"[ERR] GET failed status={st}", file=sys.stderr)
        return 2

    old_body = item.get("body", "")
    tags = item.get("tags", [])
    title = item.get("title", "")
    private = item.get("private", False)

    old_link_count = count_apify_links(old_body)
    print(f"[INFO] old apify.com links: {old_link_count}")

    new_body = build_new_body(old_body, ACTORS)
    new_link_count = count_apify_links(new_body)
    print(f"[INFO] new apify.com links: {new_link_count}")

    if new_link_count == old_link_count:
        print("[WARN] no change detected — skipping PATCH")
        return 0

    print(f"[INFO] PATCHING {ITEM_ID} ...")
    st2, resp = api_patch(token, ITEM_ID, new_body, tags=tags, title=title, private=private)
    if st2 == 200:
        print(f"[OK] PATCH HTTP {st2}")
    else:
        print(f"[FAIL] PATCH HTTP {st2} {resp}", file=sys.stderr)
        return 1

    # Read-back verification
    time.sleep(2)
    st3, item2 = api_get(token, f"{API_ITEMS}/{ITEM_ID}")
    if st3 == 200 and item2:
        verify_links = count_apify_links(item2.get("body", ""))
        print(f"[VERIFY] post-PATCH apify.com links: {verify_links}")
        if verify_links >= new_link_count:
            print("[OK] verification passed")
            return 0
        else:
            print(f"[WARN] verification mismatch: got {verify_links}, expected {new_link_count}")
            return 1
    else:
        print(f"[WARN] read-back failed status={st3}")
        return 1


if __name__ == "__main__":
    import time
    sys.exit(main())
