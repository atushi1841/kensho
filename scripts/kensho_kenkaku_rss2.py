"""KENKAKU 新着RSSから全present idを列挙し、X URLを含むページを特定。"""
from __future__ import annotations

import re
import sys
import time

import httpx

sys.path.insert(0, "/mnt/d/Project2/kensho")
from kensho.scraping.sources.common import HEADERS, _decode_response

STATUS_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/[0-9]+")

def get(url: str) -> tuple[int, str]:
    for attempt in range(5):
        try:
            with httpx.Client(follow_redirects=True, timeout=12) as c:
                resp = c.get(url, headers=dict(HEADERS))
            return resp.status_code, _decode_response(resp)
        except Exception as e:
            if attempt < 4:
                time.sleep(3)
            else:
                return 0, f"{type(e).__name__}: {e}"
    return 0, ""

feeds = {
    "index_new": "https://www.ken-kaku.com/RSS/index_new.xml",
    "index_adv": "https://www.ken-kaku.com/RSS/index_adv.xml",
}

all_ids = {}
for name, url in feeds.items():
    code, html = get(url)
    print(f"[{name}] code={code} len={len(html)}")
    ids = re.findall(r"present\.cgi\?id=(\d+)", html)
    # タイトルも拾う
    links = re.findall(r'present\.cgi\?id=(\d+)[^>]*>([^<]+)<', html)
    print(f"   ids: {len(set(ids))}")
    for i in sorted(set(ids)):
        all_ids[i] = name
    if code == 200:
        print(html[:800])
