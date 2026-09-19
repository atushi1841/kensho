"""KENKAKU収集効率監査 — 各ページのX URL出現数を分類して低取得原因を特定する。

第2収集源 ken-kaku.com の7ページを実地取得し、以下を集計:
- href(ダブル/シングルクォート)での x.com/twitter.com ステータスURL数
- 現在の正規表現(regex)で拾える数
- twitter.com / x.com ごとの内訳
- メンションURL(@user)や通常リンクの混入
- 重複(ページ間で同じstatus URLが何ページに現れるか)
"""
from __future__ import annotations

import collections
import re
import sys
import time

import httpx

sys.path.insert(0, "/mnt/d/Project2/kensho")
from kensho.scraping.sources.common import HEADERS, KENKAKU_BASE, _decode_response

_PAGE_IDS = [
    "104510000",
    "1045100010",
    "1045100020",
    "1045100030",
    "1045100040",
    "1045100050",
    "1045100060",
]

TIMEOUT = 10

# 現行コレクタの正規表現（href=" ダブルクォート fixed）
CURRENT_RE = re.compile(r'href="(https?://x\.com/[a-zA-Z0-9_]+/status/[0-9]+)"')

# 拡張: シングル/ダブル + twitter.com/x.com/あえてwww
WIDE_RE = re.compile(
    r'href=[\'"](https?://(?:www\.)?(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/[0-9]+)[\'"]'
)

PER_PAGE = collections.Counter()          # pid -> x/twitter unique status
PER_PAGE_ALL_LINKS = collections.Counter()  # pid -> total extractable status links
GLOBAL_SEEN = set()
DUPLICATE_HITS = collections.Counter()    # url -> 出現ページ数

for pid in _PAGE_IDS:
    url = f"{KENKAKU_BASE}present.cgi?id={pid}"
    r = None
    for attempt in range(6):
        try:
            with httpx.Client(follow_redirects=True, timeout=TIMEOUT) as c:
                resp = c.get(url, headers=dict(HEADERS))
            if resp.status_code == 200:
                r = resp
            break
        except Exception as e:
            if attempt < 5:
                time.sleep(3)
            else:
                print(f"[{pid}] ERROR {type(e).__name__}: {e}")
    if r is None:
        print(f"[{pid}] FETCH FAILED")
        continue
    html = _decode_response(r)
    print(f"[{pid}] html_len={len(html)} status={r.status_code} final={r.url}")

    cur = set(m.group(1) for m in CURRENT_RE.finditer(html))
    wide = set(m.group(1) for m in WIDE_RE.finditer(html))
    # 全ての status リンク (クォート問わず空引用) — x/twitter
    all_status = set(re.findall(r"https?://(?:www\.)?(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/[0-9]+", html))
    # メンション
    mentions = set(re.findall(r"https?://(?:www\.)?(?:x|twitter)\.com/[a-zA-Z0-9_]+/$", html))

    print(f"    current_re(x.com dq): {len(cur)}")
    print(f"    wide(x/tw dq/sq):     {len(wide)}")
    print(f"    all_status any-quote:  {len(all_status)}")
    print(f"    mentions(@user):      {len(mentions)}")
    PER_PAGE[pid] = len(all_status)
    PER_PAGE_ALL_LINKS[pid] = len(all_status - mentions)
    for u in all_status:
        DUPLICATE_HITS[u] += 1

# 全体の一意数と重複状況
print("\n=== ページ間一意URL数 ===")
for pid in _PAGE_IDS:
    print(f"  {pid}: {PER_PAGE[pid]}")
uniq_all = sum(c >= 1 for c in DUPLICATE_HITS.values())
dup = {u: c for u, c in DUPLICATE_HITS.items() if c > 1}
print(f"\ntotal unique status URLs across pages: {uniq_all}")
print(f"URLs appearing on >1 page: {len(dup)}")
for u, c in sorted(dup.items(), key=lambda kv: -kv[1])[:15]:
    print(f"    x{c} {u}")
