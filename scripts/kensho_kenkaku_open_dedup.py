"""全候補ページのX URLユニーク抽出 — ベースライン(その1-7)との差分を算出。"""
from __future__ import annotations

import re
import sys
import time

import httpx

sys.path.insert(0, "/mnt/d/Project2/kensho")
from kensho.scraping.sources.common import HEADERS, _decode_response

XURLS_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/[0-9]+")

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

BASE = "https://www.ken-kaku.com/cgi-bin/present/present.cgi?id="
BL   = ["104510000","1045100010","1045100020","1045100030",
        "1045100040","1045100050","1045100060"]
OPEN = ["101010000","101060000","101070000","103010000","103020000",
        "103100000","103120000","103130000","103140000",
        "104510030","104060000","104511000","104513000","104515000","104516000"]

page_urls = {}
for pid in BL + OPEN:
    code, html = get(BASE + pid)
    urls = set(XURLS_RE.findall(html))
    page_urls[pid] = urls
    print(f"  id={pid} code={code} x={len(urls)}")
    time.sleep(0.7)

baseline = set()
for b in BL:
    baseline |= page_urls[b]
print(f"\nbaseline(その1-7) unique X: {len(baseline)}")

extra_urls = {}
for pid in OPEN:
    new = page_urls[pid] - baseline
    if new:
        extra_urls[pid] = new
        print(f"  NEW from {pid}: {len(new)}")

all_new = set()
for k, v in extra_urls.items():
    all_new |= v
print(f"\n=== NEW unique X URLs beyond baseline: {len(all_new)} ===")
for u in sorted(all_new):
    print("  ", u)
