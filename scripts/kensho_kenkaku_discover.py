"""KENKAKU /cgi-bin/present/ の実ページIDを発見して、X URLを含むページを列挙する。

既知7ページは全てX URLを少数(1-5)しか含まず合計18件に頭打ち。
present.cgi?id= のID空間を調査し、強いページ(多くのX status URL)を見つける。
優しく: 各リクエスト間に sleep、失敗時は後退。
"""
from __future__ import annotations

import re
import sys
import time
import collections

import httpx

sys.path.insert(0, "/mnt/d/Project2/kensho")
from kensho.scraping.sources.common import HEADERS, _decode_response

STATUS_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/[0-9]+"
)

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

# --- 1) インデックスから present.cgi?id= リンクを列挙 ---
index_url = "https://www.ken-kaku.com/cgi-bin/present/"
code, html = get(index_url)
print(f"[INDEX] {index_url} code={code} len={len(html)}")
ids = set(re.findall(r"present\.cgi\?id=(\d+)", html))
print(f"[INDEX] {len(ids)} present ids referenced on index")

# --- 2) 既知IDの近傍をプローブ ---
known = ["104510000", "1045100010", "1045100020", "1045100030",
         "1045100040", "1045100050", "1045100060"]
base = int(known[0])
# 前後広めにプローブ: 通常 kensho ページIDは step=10 で連番
probe_ids = []
for delta in range(-500, 600, 10):
    pid = str(base + delta)
    len_pid = len(pid)
    probe_ids.append(pid)
# indexで見つかったIDを優先、既知・プローブと併合
all_ids = []
for i in sorted(ids):
    if i not in all_ids:
        all_ids.append(i)
for p in probe_ids:
    if p not in all_ids:
        all_ids.append(p)

print(f"[PROBE] total unique ids to scan: {len(all_ids)}")

results = []
KNOWN_SET = set(known)
for pid in all_ids:
    if pid in KNOWN_SET:
        # 既知はスキップ(既に0-5件と判明)
        results.append((pid, 0, "known-skip"))
        continue
    url = f"https://www.ken-kaku.com/cgi-bin/present/present.cgi?id={pid}"
    code, html = get(url)
    if code == 404 or (code == 200 and len(html) < 3000):
        # 存在しない/空ページ — 集計から外す(ノイズ削減)
        continue
    n = len(set(STATUS_RE.findall(html)))
    if n > 0:
        results.append((pid, n, "HAS-X"))
    time.sleep(1.5)  # 優しい間隔

has_x = [(pid, n) for pid, n, tag in results if tag == "HAS-X"]
print(f"\n=== {len(has_x)} pages have X URLs ===")
for pid, n in sorted(has_x, key=lambda kv: -kv[1]):
    flag = "KNOWNSET" if pid in KNOWN_SET else "NEW"
    print(f"  [{'X' if flag=='KNOWNSET' else 'N'}] id={pid} x_urls={n}")
