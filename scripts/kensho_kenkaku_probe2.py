"""KENKAKU 参照済みpresentページを網羅probe — X URL数とタイトル(そのN)を記録。"""
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

# 参照されていた一覧群(PAGE1参照リンク) + 8/9/10/11ページ目候補 + サブカテゴリ
candidates = [
    "104510000","1045100010","1045100020","1045100030","1045100040",
    "1045100050","1045100060","1045100070",                    # その1-8
    "104520000","104530000","104540000",                        # その9-11?
    "104510020","104510030","104510040","104510060","104510070","104510080",
    "104511000","104512000","104513000","104514000","104515000","104516000",
    "104010000","104020000","104030000","104040000","104050000","104060000",
    "108770000","108780000","108790000","108800000","108810000","108820000","108830000",
]

results = []
for pid in candidates:
    url = f"https://www.ken-kaku.com/cgi-bin/present/present.cgi?id={pid}"
    code, html = get(url)
    title = re.search(r"<title>([^<]*)</title>", html, re.I)
    t = title.group(1).strip() if title else ""
    n = len(set(STATUS_RE.findall(html)))
    results.append((pid, code, n, t[:42]))
    print(f"  id={pid} code={code} x={n} | {t[:42]}")
    time.sleep(0.8)

with_x = [r for r in results if r[2] > 0]
print(f"\n=== {len(with_x)} pages with X URLs ===")
total = 0
for pid, code, n, t in with_x:
    total += n
    print(f"  id={pid} x={n} | {t}")
print(f"\ntotal X urls across candidate pages: {total}")
