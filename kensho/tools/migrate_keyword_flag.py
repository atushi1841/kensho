"""既存の collected.json に keyword_flag を付与（既存データ移行用）"""

from __future__ import annotations

import concurrent.futures
import json
import sys
import time

import httpx

sys.path.insert(0, "D:/Project2/kensho")

# common.py を直接インポート（twscrape依存を回避するため）
import importlib.util

spec = importlib.util.spec_from_file_location("common", "D:/Project2/kensho/scraping/sources/common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
has_skip_keyword = common.has_skip_keyword
HEADERS = common.HEADERS
BASE_URL = common.BASE_URL
_decode_response = common._decode_response

d = json.load(open("data/collected.json"))
items: list[dict] = d.get("collected", [])
changed: int = 0

# ── knshow系（/detail/）: 詳細ページを取得してチェック ──
knshow_items: list[dict] = []
for i in items:
    if "keyword_flag" in i:
        continue
    if i.get("detail_url", "").startswith("/detail/") and "/status/" in i.get("x_url", "").lower():
        knshow_items.append(i)


def check_knshow(item: dict) -> tuple[dict, bool]:
    try:
        url: str = f"{BASE_URL}{item['detail_url']}"
        h: dict[str, str] = dict(HEADERS)
        h["Referer"] = f"{BASE_URL}/twitter"
        with httpx.Client(follow_redirects=False, timeout=15) as c:
            r = c.get(url, headers=h)
        html: str = _decode_response(r)
        return item, has_skip_keyword(html)
    except Exception:
        return item, False


done: int = 0
t0: float = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(check_knshow, item): item for item in knshow_items}
    for f in concurrent.futures.as_completed(futures):
        item, flag = f.result()
        item["keyword_flag"] = flag
        done += 1
        changed += 1 if flag else 0
        if done % 30 == 0:
            elapsed: float = time.time() - t0
            print(f"  knshow {done}/{len(knshow_items)} ... {elapsed:.0f}s")

print(f"knshow完了: {len(knshow_items)}件中{changed}件が引用/コメント応募")

# ── その他ソース: sourceフィールドがあるもの ──
other_items: list[dict] = []
for i in items:
    if "keyword_flag" in i:
        continue
    src: str = i.get("source", "")
    if (
        src in ("ken-kaku", "kenshouclub", "cpmeikan", "kema", "kensho-everyday")
        and "/status/" in i.get("x_url", "").lower()
    ):
        other_items.append(i)
    elif src == "twscrape" and "/status/" in i.get("x_url", "").lower():
        # twscrapeは元テキストがない → false
        i["keyword_flag"] = False
    elif not src and "/status/" in i.get("x_url", "").lower():
        # sourceなしでknshow非対象 = false
        i["keyword_flag"] = False


# kenkaku
def check_kenkaku(item: dict) -> tuple[dict, bool]:
    try:
        pid: str = item["detail_url"].split("id=")[1].split("/")[0] if "id=" in item["detail_url"] else "104510000"
        url: str = f"https://www.ken-kaku.com/cgi-bin/present/present.cgi?id={pid}"
        with httpx.Client(follow_redirects=False, timeout=15) as c:
            r = c.get(url, headers=dict(HEADERS))
        html: str = _decode_response(r)
        x_url: str = item["x_url"]
        pos: int = html.find(x_url)
        if pos > 0:
            ctx: str = html[max(0, pos - 600) : pos]
            return item, has_skip_keyword(ctx)
        return item, False
    except Exception:
        return item, False


kenkaku_items: list[dict] = [i for i in other_items if i.get("source") == "ken-kaku"]
kclub_items: list[dict] = [i for i in other_items if i.get("source") == "kenshouclub"]
cpmei_items: list[dict] = [i for i in other_items if i.get("source") == "cpmeikan"]
kema_items: list[dict] = [i for i in other_items if i.get("source") == "kema"]
kevery_items: list[dict] = [i for i in other_items if i.get("source") == "kensho-everyday"]

if kenkaku_items:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for f2 in concurrent.futures.as_completed({pool.submit(check_kenkaku, i): i for i in kenkaku_items}):
            i2, f2r = f2.result()
            i2["keyword_flag"] = f2r
            changed += 1 if f2r else 0
    print(f"kenkaku完了: {len(kenkaku_items)}件")


def check_kclub(item: dict) -> tuple[dict, bool]:
    try:
        article_url: str = f"https://kenshou.club{item['detail_url']}"
        with httpx.Client(follow_redirects=False, timeout=15) as c:
            r = c.get(article_url, headers=dict(HEADERS))
        html: str = _decode_response(r)
        return item, has_skip_keyword(html)
    except Exception:
        return item, False


if kclub_items:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for f3 in concurrent.futures.as_completed({pool.submit(check_kclub, i): i for i in kclub_items}):
            i3, f3r = f3.result()
            i3["keyword_flag"] = f3r
            changed += 1 if f3r else 0
    print(f"kenshouclub完了: {len(kclub_items)}件")


def check_cpmei(item: dict) -> tuple[dict, bool]:
    try:
        page: str = item["detail_url"].split("/")[-2] if "/" in item["detail_url"] else "1"
        url: str = f"https://cp.meikan.org/xcp/{page}/" if page != "1" else "https://cp.meikan.org/xcp"
        with httpx.Client(follow_redirects=False, timeout=15) as c:
            r = c.get(url, headers=dict(HEADERS))
        html: str = _decode_response(r)
        pos: int = html.find(item["x_url"])
        if pos > 0:
            ctx: str = html[max(0, pos - 800) : pos]
            return item, has_skip_keyword(ctx)
        return item, False
    except Exception:
        return item, False


if cpmei_items:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for f4 in concurrent.futures.as_completed({pool.submit(check_cpmei, i): i for i in cpmei_items}):
            i4, f4r = f4.result()
            i4["keyword_flag"] = f4r
            changed += 1 if f4r else 0
    print(f"cpmeikan完了: {len(cpmei_items)}件")


def check_kema(item: dict) -> tuple[dict, bool]:
    try:
        url: str = "https://ke-ma.net/open/"
        with httpx.Client(follow_redirects=False, timeout=15) as c:
            r = c.get(url, headers=dict(HEADERS))
        html: str = _decode_response(r)
        pos: int = html.find(item["x_url"])
        if pos > 0:
            ctx: str = html[max(0, pos - 600) : pos]
            return item, has_skip_keyword(ctx)
        return item, False
    except Exception:
        return item, False


if kema_items:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for f5 in concurrent.futures.as_completed({pool.submit(check_kema, i): i for i in kema_items}):
            i5, f5r = f5.result()
            i5["keyword_flag"] = f5r
            changed += 1 if f5r else 0
    print(f"kema完了: {len(kema_items)}件")


def check_kevery(item: dict) -> tuple[dict, bool]:
    try:
        article_url: str = f"https://kensho-everyday.com{item['detail_url']}"
        with httpx.Client(follow_redirects=False, timeout=15) as c:
            r = c.get(article_url, headers=dict(HEADERS))
        html: str = _decode_response(r)
        return item, has_skip_keyword(html)
    except Exception:
        return item, False


if kevery_items:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for f6 in concurrent.futures.as_completed({pool.submit(check_kevery, i): i for i in kevery_items}):
            i6, f6r = f6.result()
            i6["keyword_flag"] = f6r
            changed += 1 if f6r else 0
    print(f"kensho-everyday完了: {len(kevery_items)}件")

total_flag: int = sum(1 for i in items if i.get("keyword_flag", False))
print("\n=== 結果 ===")
print(f"全{len(items)}件")
print(f"  keyword_flag=true（引用/コメント応募）: {total_flag}件")
print(f"  keyword_flag=false（通常応募）: {len(items) - total_flag}件")

# 直接保存
import json as _json  # noqa: E402

with open("data/collected.json", "w", encoding="utf-8") as _f:
    _json.dump(d, _f, ensure_ascii=False, indent=2)
print("collected.json 保存完了 ✅")
