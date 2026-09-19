"""KENKAKU RSS とカテゴリページから present.cgi?id= を収集し、X URLを持つものを特定。"""
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

# RSSポータルページ
code, html = get("https://www.ken-kaku.com/rss.html")
print(f"[rss.html] code={code} len={len(html)}")
rss_links = re.findall(r'href=["\']([^"\']*(?:rss|feed)[^"\']*)["\']', html, re.I)
for l in dict.fromkeys(rss_links):
    print("   RSS:", l)

# データ配信RSSリンクを直接狙う
for cand in ["https://www.ken-kaku.com/rss.xml",
             "https://www.ken-kaku.com/feed",
             "https://www.ken-kaku.com/rss/"]:
    c2, h2 = get(cand)
    print(f"[{cand}] code={c2} len={len(h2)}")
    if c2 == 200:
        ids = re.findall(r"present\.cgi\?id=(\d+)", h2)
        print(f"   present ids in rss: {len(set(ids))}")
        for i in sorted(set(ids))[:40]:
            print("     ", i)
