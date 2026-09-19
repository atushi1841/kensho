"""KENKAKU サイト構造調査 — インデックスとカテゴリページから present.cgi?id= リンクを全列挙。"""
from __future__ import annotations

import re
import sys
import time
import collections

import httpx

sys.path.insert(0, "/mnt/d/Project2/kensho")
from kensho.scraping.sources.common import HEADERS, _decode_response

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

# 1) インデックス全内容
code, html = get("https://www.ken-kaku.com/cgi-bin/present/")
print(f"[INDEX] code={code} len={len(html)}")
print("---INDEX TEXT---")
text = re.sub(r"<[^>]+>", " ", html)
text = re.sub(r"\s+", " ", text)[:2000]
print(text)

# 全リンク
links = re.findall(r'href=["\']([^"\']+)["\']', html)
print("\n---ALL LINKS on index---")
for l in dict.fromkeys(links):
    print("  ", l)

# present.cgi?id= 一覧
ids = re.findall(r"present\.cgi\?id=(\d+)", html)
print(f"\n[INDEX ids] {len(ids)}: {sorted(set(ids))}")
