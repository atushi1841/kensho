"""RSS新着/おすすめの全present idを列挙し、各ページのX URL数を判定。"""
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
    "new": "https://www.ken-kaku.com/RSS/index_new.xml",
    "adv": "https://www.ken-kaku.com/RSS/index_adv.xml",
}
ids = []
for name, url in feeds.items():
    code, html = get(url)
    found = re.findall(r"present\.cgi\?id=(\d+)", html)
    print(f"[{name}] code={code} ids={len(found)}")
    ids.extend(found)

# ユニーク化（順序保持）
seen = set()
uniq = [i for i in ids if not (i in seen or seen.add(i))]
print(f"total unique ids: {len(uniq)}")

results = []
for pid in uniq:
    url = f"https://www.ken-kaku.com/cgi-bin/present/present.cgi?id={pid}"
    code, html = get(url)
    n = len(set(STATUS_RE.findall(html)))
    results.append((pid, code, n, len(html)))
    print(f"  id={pid} code={code} len={len(html)} x_urls={n}")
    time.sleep(1.2)

with_x = [r for r in results if r[2] > 0]
print(f"\n=== {len(with_x)}/{len(results)} present pages have X URLs ===")
for pid, code, n, l in with_x:
    print(f"  id={pid} x_urls={n}")
