"""既知KENKAKUページのフル構造調査 — Xキャンペーン系列のナビ/一覧/ページングを見つける。"""
from __future__ import annotations

import re
import sys
import time

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

pid = "1045100010"
url = f"https://www.ken-kaku.com/cgi-bin/present/present.cgi?id={pid}"
code, html = get(url)
print(f"[{pid}] code={code} len={len(html)}")

# 全リンク（present系以外も）
links = re.findall(r'href=["\']([^"\']+)["\']', html)
print("--- ALL LINKS ---")
for l in dict.fromkeys(links):
    print("  ", l)

# present ids 参照
present_ids = re.findall(r"present\.cgi\?id=(\d+)", html)
print(f"\n--- present ids referenced: {len(set(present_ids))} ---")
for i in sorted(set(present_ids)):
    print("  ", i)

# X URL 抽出（様式違いも含む）
all_x = re.findall(r"https?://(?:www\.)?(?:x|twitter)\.com/(?:[a-zA-Z0-9_]+/status/[0-9]+|[a-zA-Z0-9_]+)", html)
print(f"\n--- x/twitter links: {len(set(all_x))} ---")
for x in sorted(set(all_x))[:30]:
    print("  ", x)

# カテゴリ判定用に見出し/タイトル
t = re.search(r"<title>([^<]*)</title>", html, re.I)
print(f"\n<title>: {t.group(1) if t else None}")
