"""候補ページ群のX URLユニーク数をページ組み合わせ別に算出（重複排除）。"""
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

# ページ別のユニークX URL
page_urls = {}
candidates = [
    ("MAIN-1",  "104510000"), ("MAIN-2",  "1045100010"), ("MAIN-3",  "1045100020"),
    ("MAIN-4",  "1045100030"), ("MAIN-5",  "1045100040"), ("MAIN-6",  "1045100050"),
    ("MAIN-7",  "1045100060"), ("MAIN-8",  "1045100070"),
    ("SORT-OSEKOMI", "104511000"), ("SORT-WIN", "104513000"), ("SORT-SHAIDEADLINE", "104515000"), ("SORT-FEWWIN", "104516000"),
    ("EXTRA-104510030", "104510030"), ("QUIZ", "104060000"),
    ("DL-0920", "108780000"), ("DL-0921", "108790000"), ("DL-0922", "108800000"), ("DL-0923", "108810000"), ("DL-0925", "108830000"),
]
for name, pid in candidates:
    code, html = get(BASE + pid)
    urls = set(XURLS_RE.findall(html))
    page_urls[name] = urls
    print(f"  {name:22s} id={pid} x_urls={len(urls)}")
    time.sleep(0.8)

MAIN = [f"MAIN-{i}" for i in range(1, 9)]
ALL_NONDATE = [n for n, _ in candidates if n != "DL-0920" and not n.startswith("DL-")]

def uniq(keys):
    s = set()
    for k in keys:
        s |= page_urls[k]
    return s

print("\n--- 組み合わせ別ユニークX URL数 ---")
cur = uniq(["MAIN-1","MAIN-2","MAIN-3","MAIN-4","MAIN-5","MAIN-6","MAIN-7"])
print(f"current(その1-7)  : {len(cur)}")
print(f"+ その8           : {len(uniq([f'MAIN-{i}' for i in range(1,9)]))}")
all_main = uniq([f"MAIN-{i}" for i in range(1,9)])
print(f"  main(その1-8)   : {len(all_main)}")
add_sort = uniq([f"MAIN-{i}" for i in range(1,9)] + ["SORT-OSEKOMI","SORT-WIN","SORT-SHAIDEADLINE","SORT-FEWWIN"])
print(f"  main+sort       : {len(add_sort)}")
add_extra = uniq([f"MAIN-{i}" for i in range(1,9)] + ["SORT-OSEKOMI","SORT-WIN","SORT-SHAIDEADLINE","SORT-FEWWIN","EXTRA-104510030","QUIZ"])
print(f"  main+sort+extra : {len(add_extra)}")
all_dl = uniq([f"MAIN-{i}" for i in range(1,9)] + ["SORT-OSEKOMI","SORT-WIN","SORT-SHAIDEADLINE","SORT-FEWWIN","EXTRA-104510030","QUIZ"] + [f"DL-09{i}" for i in range(20,24)] + ["DL-0925"])
print(f"  +deadline views : {len(all_dl)}")

# 現在の7ページから見た新規追加分
marginal = add_extra - cur
print(f"\nmain+sort+extra で現在(その1-7)に無い新規")
print(f"新規ユニークX URL: {len(marginal)}")
for u in sorted(marginal):
    print("  ", u)
